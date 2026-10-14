"""Execute the actual Editor helper with stubbed Unity APIs; no Unity/robot launch."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
CSC = Path(os.environ.get('WINDIR', r'C:\Windows')) / 'Microsoft.NET/Framework64/v4.0.30319/csc.exe'

STUBS = r'''
namespace UnityEngine {
 public static class Application { public static string dataPath; }
 public static class Debug {
  public static void Log(object x) { Console.WriteLine(x); }
  public static void LogWarning(object x) { Console.WriteLine(x); }
  public static void LogError(object x) { Console.WriteLine(x); }
 }
}
namespace UnityEngine.SceneManagement {
 public struct Scene { public string path; }
 public static class SceneManager {
  public static int sceneCount=1;
  public static string Active="Assets/Scenes/Other.unity";
  public static Scene GetActiveScene() { return new Scene {path=Active}; }
 }
}
namespace UnityEditor {
 public class InitializeOnLoadAttribute : Attribute { }
 public class SceneAsset { }
 public static class AssetDatabase {
  public static bool Exists=true;
  public static T LoadAssetAtPath<T>(string path) where T : class, new() {
   return Exists ? new T() : null;
  }
 }
 public static class EditorUtility { public static bool scriptCompilationFailed; }
 public static class EditorApplication {
  public static event Action update;
  public static event Action quitting;
  public static bool isCompiling, isUpdating, isPlayingOrWillChangePlaymode, isPlaying;
  public static void Quit() { if(quitting!=null) quitting(); }
 }
}
namespace UnityEditor.SceneManagement {
 public enum OpenSceneMode { Single }
 public static class EditorSceneManager {
  public static bool Allow=true, Throw=false;
  public static int Opens, Prompts;
  public static bool SaveCurrentModifiedScenesIfUserWantsTo() { Prompts++; return Allow; }
  public static void OpenScene(string path, OpenSceneMode mode) {
   if(Throw) throw new Exception("fixture scene open failure");
   Opens++;
   UnityEngine.SceneManagement.SceneManager.Active=path;
   UnityEngine.SceneManagement.SceneManager.sceneCount=1;
  }
 }
}
public static class Fixture {
 static string request;
 static void Check(bool ok,string reason) { if(!ok) throw new Exception(reason); }
 static void Tick() {
  typeof(G1TeleopAutoPlay).GetMethod("TryConsumeRequest",System.Reflection.BindingFlags.NonPublic|System.Reflection.BindingFlags.Static).Invoke(null,null);
 }
 static void Fresh() {
  UnityEditor.EditorApplication.isPlaying=false;
  File.WriteAllText(request,DateTimeOffset.UtcNow.ToUnixTimeSeconds().ToString());
 }
 public static void Main(string[] args) {
  UnityEngine.Application.dataPath=Path.Combine(args[0],"Assets");
  Directory.CreateDirectory(UnityEngine.Application.dataPath);
  Directory.CreateDirectory(Path.Combine(args[0],"Library"));
  request=Path.Combine(args[0],"Library/G1TeleopAutoPlay.request");
  Check(G1TeleopAutoPlay.RequestIsCurrent("1000",11800,1001),"three-hour first import expired");
  Check(!G1TeleopAutoPlay.RequestIsCurrent("1000",11800,11700),"previous Editor request accepted");
  Check(!G1TeleopAutoPlay.RequestIsCurrent("bad",11800,1001),"invalid accepted");
  Check(!G1TeleopAutoPlay.RequestIsCurrent("11831",11800,1001),"future accepted");
  Fresh(); UnityEditor.EditorApplication.isCompiling=true; Tick();
  Check(File.Exists(request)&&!UnityEditor.EditorApplication.isPlaying,"compile wait failed");
  UnityEditor.EditorApplication.isCompiling=false;
  UnityEditor.EditorApplication.isUpdating=true; Tick();
  Check(File.Exists(request)&&!UnityEditor.EditorApplication.isPlaying,"import wait failed");
  UnityEditor.EditorApplication.isUpdating=false; Tick();
  Check(UnityEditor.EditorApplication.isPlaying,"fresh import did not play");
  Check(UnityEngine.SceneManagement.SceneManager.Active=="Assets/Scenes/SampleScene.unity","wrong scene played");
  Check(!File.Exists(request),"request not consumed");
  int opens=UnityEditor.SceneManagement.EditorSceneManager.Opens;
  Fresh(); Tick(); Check(UnityEditor.SceneManagement.EditorSceneManager.Opens==opens,"reopened existing scene");
  UnityEngine.SceneManagement.SceneManager.Active="Other";
  UnityEditor.SceneManagement.EditorSceneManager.Allow=false;
  Fresh(); Tick(); Check(!UnityEditor.EditorApplication.isPlaying&&!File.Exists(request),"cancel ignored");
  UnityEditor.SceneManagement.EditorSceneManager.Allow=true;
  UnityEditor.AssetDatabase.Exists=false;
  Fresh(); Tick(); Check(!UnityEditor.EditorApplication.isPlaying,"missing scene played");
  UnityEditor.AssetDatabase.Exists=true;
  UnityEditor.EditorUtility.scriptCompilationFailed=true;
  Fresh(); Tick(); Check(!UnityEditor.EditorApplication.isPlaying,"compile failure played");
  UnityEditor.EditorUtility.scriptCompilationFailed=false;
  UnityEditor.SceneManagement.EditorSceneManager.Throw=true;
  Fresh(); Tick(); Check(!UnityEditor.EditorApplication.isPlaying,"open failure played");
  UnityEditor.SceneManagement.EditorSceneManager.Throw=false;
  UnityEditor.EditorApplication.isPlayingOrWillChangePlaymode=true;
  Fresh(); Tick(); Check(UnityEngine.SceneManagement.SceneManager.Active=="Other","running scene replaced");
  UnityEditor.EditorApplication.isPlayingOrWillChangePlaymode=false;
  Fresh(); UnityEditor.EditorApplication.Quit(); Check(!File.Exists(request),"quit left request");
  Console.WriteLine("PASS: actual AutoPlay source, mocked Editor scene lifecycle");
 }
}
'''


@unittest.skipUnless(CSC.is_file(), 'requires Windows .NET C# compiler')
class AutoPlayTests(unittest.TestCase):
    def test_actual_csharp_lifecycle_and_cold_import(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            fixture = work / 'fixture.cs'
            fixture.write_text('using System;using System.IO;\n' + STUBS, encoding='utf-8')
            exe = work / 'fixture.exe'
            source = ROOT / 'Unity_G1_VR/Assets/Editor/G1TeleopAutoPlay.cs'
            result = subprocess.run([str(CSC), '/nologo', '/out:' + str(exe), str(source), str(fixture)],
                                    capture_output=True, timeout=30)
            self.assertEqual(0, result.returncode, result.stdout.decode(errors='replace'))
            result = subprocess.run([str(exe), str(work / 'project')], capture_output=True, timeout=15)
            self.assertEqual(0, result.returncode, result.stdout.decode(errors='replace') + result.stderr.decode(errors='replace'))
            self.assertIn(b'PASS: actual AutoPlay source', result.stdout)


if __name__ == '__main__':
    unittest.main()
