// Pensieve desktop launcher.
//
// Double-click to open Pensieve in its own app window. The launcher:
//   1. finds the repo, its .venv Python, and the port from .env
//   2. starts the FastAPI backend hidden (unless one is already running)
//   3. opens Microsoft Edge in app mode (no tabs, no address bar) on a
//      dedicated profile, showing a splash page until the backend answers
//   4. waits until every Pensieve window is closed, then stops the backend
//      it started (a backend it found already running is left alone)
//
// Built by build.ps1 with the .NET Framework C# compiler (C# 5 syntax only).
// Logs: %LOCALAPPDATA%\Pensieve\logs\

using System;
using System.Diagnostics;
using System.IO;
using System.Management;
using System.Net;
using System.Text;
using System.Threading;
using System.Windows.Forms;
using Microsoft.Win32;

[assembly: System.Reflection.AssemblyTitle("Pensieve")]
[assembly: System.Reflection.AssemblyProduct("Pensieve")]
[assembly: System.Reflection.AssemblyDescription("Pensieve desktop launcher")]
[assembly: System.Reflection.AssemblyVersion("1.0.0.0")]

namespace PensieveDesktop
{
    static class Program
    {
        // Replaced by build.ps1 so a copied or moved exe still finds the repo.
        const string BakedRepoRoot = "@@REPO_ROOT@@";

        const string MutexName = "Local\\PensieveDesktopLauncher";
        const string ProfileMarker = "Pensieve\\EdgeProfile";

        static string appDataDir;
        static string logDir;
        static readonly object logLock = new object();
        static StreamWriter serverLog;

        [STAThread]
        static int Main(string[] args)
        {
            appDataDir = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "Pensieve");
            logDir = Path.Combine(appDataDir, "logs");
            Directory.CreateDirectory(logDir);
            try
            {
                return Run();
            }
            catch (Exception ex)
            {
                Log("fatal: " + ex);
                Fail("Pensieve hit an unexpected error:\n\n" + ex.Message);
                return 1;
            }
        }

        static int Run()
        {
            string repo = ResolveRepoRoot();
            if (repo == null)
            {
                Fail("Could not find the Pensieve folder.\n\nSet the PENSIEVE_HOME environment variable to the repo folder, or rebuild the launcher with desktop\\build.ps1.");
                return 2;
            }

            string python = ResolvePython(repo);
            if (python == null)
            {
                Fail("Could not find Python for Pensieve.\n\nExpected " + Path.Combine(repo, ".venv\\Scripts\\python.exe") + " (or set PENSIEVE_PYTHON).");
                return 2;
            }

            string edge = FindEdge();
            if (edge == null)
            {
                Fail("Microsoft Edge was not found. Pensieve uses Edge to draw its window.");
                return 2;
            }

            int port = ReadPort(repo);
            string baseUrl = "http://127.0.0.1:" + port + "/";
            string profileDir = Path.Combine(appDataDir, "EdgeProfile");
            Log(string.Format("start: repo={0} python={1} port={2}", repo, python, port));

            bool createdNew;
            using (Mutex mutex = new Mutex(true, MutexName, out createdNew))
            {
                if (!createdNew)
                {
                    // Another launcher already owns the backend; just open a window.
                    Log("another launcher is running; opening a window only");
                    LaunchEdge(edge, profileDir, baseUrl);
                    return 0;
                }

                Process server = null;
                if (IsHealthy(baseUrl))
                {
                    Log("backend already running; will leave it running on exit");
                    LaunchEdge(edge, profileDir, baseUrl);
                }
                else
                {
                    server = StartServer(repo, python, port);
                    string splash = WriteSplash(repo, baseUrl);
                    LaunchEdge(edge, profileDir, new Uri(splash).AbsoluteUri);
                    if (!WaitHealthy(baseUrl, server, TimeSpan.FromSeconds(120)))
                    {
                        StopServer(server, baseUrl);
                        Fail("The Pensieve backend did not start.\n\nDetails are in:\n" + Path.Combine(logDir, "server.log"));
                        return 1;
                    }
                    Log("backend healthy");
                }

                WaitForWindowsToClose(profileDir);
                Log("all Pensieve windows closed");

                if (server != null)
                {
                    StopServer(server, baseUrl);
                }
                mutex.ReleaseMutex();
            }
            return 0;
        }

        // ---- Locating things ------------------------------------------------

        static bool IsRepoRoot(string dir)
        {
            return dir != null
                && File.Exists(Path.Combine(dir, "pyproject.toml"))
                && File.Exists(Path.Combine(dir, "pensieve\\__init__.py"))
                && Directory.Exists(Path.Combine(dir, "frontend-proto"));
        }

        static string ResolveRepoRoot()
        {
            string env = Environment.GetEnvironmentVariable("PENSIEVE_HOME");
            if (!string.IsNullOrEmpty(env) && IsRepoRoot(env)) return env;

            string dir = AppDomain.CurrentDomain.BaseDirectory;
            for (int i = 0; i < 4 && dir != null; i++)
            {
                if (IsRepoRoot(dir)) return dir.TrimEnd('\\');
                DirectoryInfo parent = Directory.GetParent(dir.TrimEnd('\\'));
                dir = parent == null ? null : parent.FullName;
            }

            if (IsRepoRoot(BakedRepoRoot)) return BakedRepoRoot;
            return null;
        }

        static string ResolvePython(string repo)
        {
            string env = Environment.GetEnvironmentVariable("PENSIEVE_PYTHON");
            if (!string.IsNullOrEmpty(env) && File.Exists(env)) return env;
            string venv = Path.Combine(repo, ".venv\\Scripts\\python.exe");
            return File.Exists(venv) ? venv : null;
        }

        static string FindEdge()
        {
            string[] keys = {
                "SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\App Paths\\msedge.exe",
                "SOFTWARE\\WOW6432Node\\Microsoft\\Windows\\CurrentVersion\\App Paths\\msedge.exe"
            };
            foreach (string k in keys)
            {
                using (RegistryKey rk = Registry.LocalMachine.OpenSubKey(k))
                {
                    if (rk != null)
                    {
                        string p = rk.GetValue(null) as string;
                        if (!string.IsNullOrEmpty(p) && File.Exists(p)) return p;
                    }
                }
            }
            string[] guesses = {
                Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFilesX86), "Microsoft\\Edge\\Application\\msedge.exe"),
                Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles), "Microsoft\\Edge\\Application\\msedge.exe")
            };
            foreach (string g in guesses)
            {
                if (File.Exists(g)) return g;
            }
            return null;
        }

        static int ReadPort(string repo)
        {
            string envFile = Path.Combine(repo, ".env");
            if (File.Exists(envFile))
            {
                foreach (string raw in File.ReadAllLines(envFile))
                {
                    string line = raw.Trim();
                    if (!line.StartsWith("PENSIEVE_BACKEND_PORT")) continue;
                    int eq = line.IndexOf('=');
                    int port;
                    if (eq > 0 && int.TryParse(line.Substring(eq + 1).Trim(), out port) && port > 0) return port;
                }
            }
            return 8765;
        }

        // ---- Backend --------------------------------------------------------

        static Process StartServer(string repo, string python, int port)
        {
            string logPath = Path.Combine(logDir, "server.log");
            try
            {
                if (File.Exists(logPath) && new FileInfo(logPath).Length > 5 * 1024 * 1024)
                {
                    File.Copy(logPath, logPath + ".1", true);
                    File.Delete(logPath);
                }
            }
            catch (IOException) { }
            serverLog = new StreamWriter(logPath, true, new UTF8Encoding(false));
            serverLog.AutoFlush = true;
            serverLog.WriteLine();
            serverLog.WriteLine("==== " + DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss") + " starting backend on port " + port + " ====");

            ProcessStartInfo psi = new ProcessStartInfo(python, "-m pensieve.cli serve --port " + port);
            psi.WorkingDirectory = repo;
            psi.UseShellExecute = false;
            psi.CreateNoWindow = true;
            psi.RedirectStandardOutput = true;
            psi.RedirectStandardError = true;
            psi.StandardOutputEncoding = Encoding.UTF8;
            psi.StandardErrorEncoding = Encoding.UTF8;
            psi.EnvironmentVariables["PYTHONPATH"] = repo;
            psi.EnvironmentVariables["PYTHONUNBUFFERED"] = "1";
            psi.EnvironmentVariables["PYTHONIOENCODING"] = "utf-8";
            psi.EnvironmentVariables["PYTHONUTF8"] = "1";

            Process p = new Process();
            p.StartInfo = psi;
            p.OutputDataReceived += OnServerOutput;
            p.ErrorDataReceived += OnServerOutput;
            p.Start();
            p.BeginOutputReadLine();
            p.BeginErrorReadLine();
            Log("backend started, pid " + p.Id);
            return p;
        }

        static void OnServerOutput(object sender, DataReceivedEventArgs e)
        {
            if (e.Data == null) return;
            lock (logLock)
            {
                try { serverLog.WriteLine(e.Data); } catch (Exception) { }
            }
        }

        static string HttpGet(string url, int timeoutMs)
        {
            HttpWebRequest req = (HttpWebRequest)WebRequest.Create(url);
            req.Proxy = null; // loopback only; skip proxy auto-detection
            req.Timeout = timeoutMs;
            req.ReadWriteTimeout = timeoutMs;
            using (HttpWebResponse resp = (HttpWebResponse)req.GetResponse())
            using (StreamReader sr = new StreamReader(resp.GetResponseStream()))
            {
                return sr.ReadToEnd();
            }
        }

        // Windows takes about 2 s to refuse a connection to a closed loopback
        // port, so a plain HTTP probe pads every check while the backend is
        // still starting. A short TCP connect answers "nobody listening" fast.
        static bool PortOpen(int port, int timeoutMs)
        {
            using (System.Net.Sockets.TcpClient c = new System.Net.Sockets.TcpClient())
            {
                try
                {
                    IAsyncResult ar = c.BeginConnect("127.0.0.1", port, null, null);
                    if (!ar.AsyncWaitHandle.WaitOne(timeoutMs)) return false;
                    c.EndConnect(ar);
                    return true;
                }
                catch (Exception)
                {
                    return false;
                }
            }
        }

        static bool IsHealthy(string baseUrl)
        {
            if (!PortOpen(new Uri(baseUrl).Port, 250)) return false;
            try
            {
                string body = HttpGet(baseUrl + "api/healthz", 1500);
                return body.Contains("\"ok\":true") || body.Contains("\"ok\": true");
            }
            catch (Exception)
            {
                return false;
            }
        }

        static bool WaitHealthy(string baseUrl, Process server, TimeSpan timeout)
        {
            DateTime deadline = DateTime.UtcNow + timeout;
            while (DateTime.UtcNow < deadline)
            {
                if (server.HasExited)
                {
                    Log("backend exited early with code " + server.ExitCode);
                    return false;
                }
                if (IsHealthy(baseUrl)) return true;
                Thread.Sleep(200);
            }
            Log("backend did not become healthy in time");
            return false;
        }

        static void StopServer(Process server, string baseUrl)
        {
            if (server == null || server.HasExited) return;

            // Let an in-flight sync finish so Chroma is not cut off mid-write.
            DateTime deadline = DateTime.UtcNow + TimeSpan.FromSeconds(90);
            while (DateTime.UtcNow < deadline)
            {
                string status;
                try { status = HttpGet(baseUrl + "api/sync/status", 2000); }
                catch (Exception) { break; }
                if (!status.Contains("\"status\":\"running\"")) break;
                Log("waiting for running sync to finish before stopping");
                Thread.Sleep(2000);
            }

            try
            {
                ProcessStartInfo kill = new ProcessStartInfo("taskkill", "/PID " + server.Id + " /T /F");
                kill.UseShellExecute = false;
                kill.CreateNoWindow = true;
                Process.Start(kill).WaitForExit(10000);
            }
            catch (Exception ex)
            {
                Log("taskkill failed: " + ex.Message);
                try { server.Kill(); } catch (Exception) { }
            }
            Log("backend stopped");
        }

        // ---- Window ---------------------------------------------------------

        static void LaunchEdge(string edge, string profileDir, string url)
        {
            Directory.CreateDirectory(profileDir);
            string args = string.Format(
                "--app=\"{0}\" --user-data-dir=\"{1}\" --no-first-run --no-default-browser-check --window-size=1500,950",
                url, profileDir);
            ProcessStartInfo psi = new ProcessStartInfo(edge, args);
            psi.UseShellExecute = false;
            Process.Start(psi);
            Log("opened window: " + url);
        }

        static int CountPensieveEdgeProcesses(string profileDir)
        {
            int n = 0;
            string marker = profileDir.ToLowerInvariant();
            using (ManagementObjectSearcher s = new ManagementObjectSearcher(
                "SELECT CommandLine FROM Win32_Process WHERE Name = 'msedge.exe'"))
            using (ManagementObjectCollection results = s.Get())
            {
                foreach (ManagementObject mo in results)
                {
                    string cmd = mo["CommandLine"] as string;
                    if (cmd == null) continue;
                    string lc = cmd.ToLowerInvariant();
                    if (lc.Contains(marker) || lc.Contains(ProfileMarker.ToLowerInvariant())) n++;
                    mo.Dispose();
                }
            }
            return n;
        }

        static void WaitForWindowsToClose(string profileDir)
        {
            // Give Edge a moment to appear, then wait for it to go away.
            DateTime appearDeadline = DateTime.UtcNow + TimeSpan.FromSeconds(30);
            while (DateTime.UtcNow < appearDeadline && CountPensieveEdgeProcesses(profileDir) == 0)
            {
                Thread.Sleep(500);
            }
            while (CountPensieveEdgeProcesses(profileDir) > 0)
            {
                Thread.Sleep(2000);
            }
        }

        static string WriteSplash(string repo, string baseUrl)
        {
            string path = Path.Combine(appDataDir, "splash.html");
            string icon = Path.Combine(repo, "desktop\\pensieve.ico");
            string video = Path.Combine(repo, "frontend-proto\\assets\\splash-loop.mp4");
            string poster = Path.Combine(repo, "frontend-proto\\assets\\splash-poster.webp");
            string html = SplashHtml
                .Replace("@@TARGET@@", baseUrl)
                .Replace("@@ICON@@", FileUri(icon))
                .Replace("@@VIDEO@@", FileUri(video))
                .Replace("@@POSTER@@", FileUri(poster));
            File.WriteAllText(path, html, new UTF8Encoding(false));
            return path;
        }

        static string FileUri(string path)
        {
            return File.Exists(path) ? new Uri(path).AbsoluteUri : "";
        }

        // ---- Diagnostics ----------------------------------------------------

        static void Log(string msg)
        {
            try
            {
                lock (logLock)
                {
                    File.AppendAllText(Path.Combine(logDir, "launcher.log"),
                        DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss") + "  " + msg + Environment.NewLine);
                }
            }
            catch (Exception) { }
        }

        static void Fail(string msg)
        {
            Log("error shown: " + msg.Replace("\n", " "));
            MessageBox.Show(msg, "Pensieve", MessageBoxButtons.OK, MessageBoxIcon.Warning);
        }

        // Shown while the backend warms up. Polls the health endpoint and
        // swaps itself for the dashboard as soon as the backend answers.
        const string SplashHtml = @"<!doctype html>
<html lang=""en"">
<head>
<meta charset=""utf-8"">
<title>The Pensieve</title>
<link rel=""icon"" href=""@@ICON@@"">
<link rel=""preconnect"" href=""https://fonts.googleapis.com"">
<link rel=""preconnect"" href=""https://fonts.gstatic.com"" crossorigin>
<link href=""https://fonts.googleapis.com/css2?family=Cinzel:wght@500;700&family=IM+Fell+English:ital@1&display=swap"" rel=""stylesheet"">
<style>
  html, body { margin: 0; height: 100%; }
  body {
    display: flex; align-items: center; justify-content: center; flex-direction: column;
    background: radial-gradient(ellipse at 50% 40%, #121a36 0%, #070a17 55%, #03050c 100%);
    color: #e9cf8a; font-family: 'Cinzel', 'Georgia', serif;
    transition: opacity 320ms ease;
  }
  body.leaving { opacity: 0; }
  /* screen blend drops the clip's near-black backdrop into the page gradient;
     it sits on the masked container because a mask isolates its children */
  .bowl {
    width: min(46vmin, 380px); aspect-ratio: 1; margin-bottom: 0.6rem; mix-blend-mode: screen;
    -webkit-mask-image: radial-gradient(circle at 50% 50%, #000 52%, transparent 71%);
            mask-image: radial-gradient(circle at 50% 50%, #000 52%, transparent 71%);
  }
  .bowl video { width: 100%; height: 100%; object-fit: cover; display: block; }
  h1 {
    font-size: clamp(1.8rem, 4.2vmin, 2.6rem); letter-spacing: 0.14em; margin: 0 0 0.5rem;
    font-weight: 700; text-shadow: 0 0 18px rgba(233, 207, 138, 0.35);
  }
  p { font-family: 'IM Fell English', 'Georgia', serif; font-style: italic; color: #cdbf9f; margin: 0.2rem 0; letter-spacing: 0.02em; }
  #slow { margin-top: 1rem; font-size: 0.9rem; color: #9f977f; }
  @media (prefers-reduced-motion: reduce) { body { transition: none; } }
</style>
</head>
<body>
  <div class=""bowl"" aria-hidden=""true"">
    <video src=""@@VIDEO@@"" poster=""@@POSTER@@"" autoplay muted loop playsinline></video>
  </div>
  <h1>The Pensieve</h1>
  <p>Stirring the surface...</p>
  <p id=""slow"" hidden>Still gathering memories. The first start after a reboot can take a little longer.</p>
<script>
  var target = '@@TARGET@@';
  var shownAt = Date.now();
  var MIN_SHOW_MS = 1400; // long enough to read as a splash, never a flash
  var tries = 0;
  if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    var v = document.querySelector('video');
    if (v) { v.removeAttribute('autoplay'); v.pause(); }
  }
  function go() {
    var wait = Math.max(0, MIN_SHOW_MS - (Date.now() - shownAt));
    setTimeout(function () {
      document.body.classList.add('leaving');
      setTimeout(function () { location.replace(target); }, 300);
    }, wait);
  }
  function poll() {
    tries++;
    fetch(target + 'api/healthz', { mode: 'no-cors', cache: 'no-store' })
      .then(go)
      .catch(function () {
        if (tries === 40) document.getElementById('slow').hidden = false;
        setTimeout(poll, 500);
      });
  }
  poll();
</script>
</body>
</html>";
    }
}
