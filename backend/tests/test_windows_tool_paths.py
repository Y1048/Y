"""Offline Windows path discovery; copied BATs, inert files, no editor/device I/O."""
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
LAUNCHERS = (
    'START_VR_HAND_TO_MUJOCO.bat',
    'tools/BUILD_AND_INSTALL_VR_APK.bat',
    'tools/TEST_CAMERA_REPLAY_TO_UNITY.bat',
    'tools/TEST_G1_MINK_FK_PARITY.bat',
)
HELPER = 'tools/RESOLVE_UNITY_EDITOR.bat'
RELATIVE_EDITOR = Path('Unity/Hub/Editor/6000.5.4f1/Editor/Unity.exe')
CMD = os.environ.get('COMSPEC') or shutil.which('cmd.exe')


class PathContractTests(unittest.TestCase):
    def test_path_only_check_precedes_every_original_action(self):
        for name in LAUNCHERS:
            lines = (ROOT/name).read_text(encoding='utf-8').splitlines()
            commands = [line.strip() for line in lines if line.strip()
                        and not line.lstrip().lower().startswith('rem ')]
            helper = r'%~dp0tools\RESOLVE_UNITY_EDITOR.bat' if '/' not in name else r'%~dp0RESOLVE_UNITY_EDITOR.bat'
            self.assertEqual(commands[:4], [
                '@echo off', 'setlocal EnableExtensions DisableDelayedExpansion',
                'call "'+helper+'" "%~1"',
                'if /I "%~1"=="--check-unity-path" exit /b %ERRORLEVEL%'])
            self.assertNotIn('set "UNITY_EXE=', '\n'.join(commands[4:]))
            self.assertIn('Unity 6000.5.4f1 was not found', '\n'.join(commands))

    def test_helper_has_no_execution_or_installation_commands(self):
        text = (ROOT/HELPER).read_text(encoding='utf-8')
        commands = [line.strip().lower() for line in text.splitlines() if line.strip()
                    and not line.lstrip().lower().startswith('rem ')]
        for command in commands:
            self.assertTrue(command.startswith(('@echo off', 'set ', 'if ', 'goto ', ':', 'exit /b ')), command)
        self.assertIn('6000.5.4f1', text)

    def test_windows_entrypoints_have_no_fixed_user_or_install_drive(self):
        paths = list(ROOT.glob('*.bat'))
        for directory in ('tools', 'experiments/twist2_right_arm_manual'):
            for suffix in ('*.bat', '*.cmd', '*.ps1'):
                paths.extend((ROOT/directory).glob(suffix))
        pattern = re.compile(r'[A-Za-z]:[\\/](?:Users|Program Files)', re.I)
        for path in paths:
            self.assertIsNone(pattern.search(path.read_text(encoding='utf-8-sig')), str(path))


@unittest.skipUnless(os.name == 'nt' and CMD, 'Requires Windows cmd.exe; no Unity dependency')
class UnityEditorDiscoveryTests(unittest.TestCase):
    def setUp(self):
        # Abort before starting any BAT if its early exit contract changed.
        PathContractTests('test_path_only_check_precedes_every_original_action').test_path_only_check_precedes_every_original_action()
        self.temp = tempfile.TemporaryDirectory(prefix='g1 tool paths ')
        self.addCleanup(self.temp.cleanup)
        self.workspace = Path(self.temp.name)
        self.checkout = self.workspace/'checkout (offline)'
        for name in (*LAUNCHERS, HELPER):
            target = self.checkout/name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT/name, target)
        self.program_files = self.workspace/'Program Files (test)'
        self.profile = self.workspace/'Profiles'/'portable tester'
        self.program_editor = self.program_files/RELATIVE_EDITOR
        self.profile_editor = self.profile/RELATIVE_EDITOR
        self.custom_editor = self.workspace/'Custom Editor'/'Unity.exe'
        self.guard = self.workspace/'unexpected-execution.txt'
        trap_dir = self.workspace/'guard-bin'
        trap_dir.mkdir()
        for command in ('py','python','powershell','wsl','adb','cl','netstat','tasklist','timeout'):
            (trap_dir/(command+'.bat')).write_text('@echo off\r\necho blocked>"%TEST_EXECUTION_GUARD%"\r\nexit /b 99\r\n', encoding='ascii')
        self.env = {k:v for k,v in os.environ.items() if k.upper() not in
                    {'UNITY_EXE','UNITY_EXE_SOURCE','PROGRAMFILES','USERPROFILE'}}
        self.env.update(ProgramFiles=str(self.program_files), USERPROFILE=str(self.profile),
                        TEST_EXECUTION_GUARD=str(self.guard), PATH=str(trap_dir))

    def create_inert_file(self, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'Not executable: path-resolution fixture only.\n')

    def check_all(self, expected, source=None, extra_env=None, delayed=False):
        env = dict(self.env)
        if extra_env:
            env.update(extra_env)
        for launcher in LAUNCHERS:
            with self.subTest(launcher=launcher):
                command = 'call "'+str(self.checkout/launcher)+'" --check-unity-path'
                # cmd.exe does not use the C-runtime backslash quote escaping of list2cmdline.
                arguments = subprocess.list2cmdline([CMD])+' /d /u '+('/v:on' if delayed else '/v:off')+' /c '+command
                completed = subprocess.run(arguments,
                    cwd=self.workspace, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
                stdout = completed.stdout.decode('utf-16-le', errors='replace')
                stderr = completed.stderr.decode('utf-16-le', errors='replace')
                self.assertFalse(self.guard.exists(), stdout+stderr)
                self.assertEqual(completed.returncode, 0 if expected is not None else 1, stdout+stderr)
                self.assertFalse((self.checkout/'logs').exists())
                self.assertFalse((self.checkout/'Builds').exists())
                if expected is None:
                    self.assertIn('Unity 6000.5.4f1 was not found.', stdout)
                    self.assertNotIn('UNITY_EXE=', stdout)
                else:
                    values = dict(line.split('=',1) for line in stdout.splitlines() if '=' in line)
                    self.assertEqual(values.get('UNITY_EXE'), str(expected), stdout)
                    self.assertEqual(values.get('UNITY_EXE_SOURCE'), source, stdout)
                    self.assertNotIn('[ERROR]', stdout)

    def test_existing_override_wins_over_both_defaults(self):
        for path in (self.custom_editor,self.program_editor,self.profile_editor):
            self.create_inert_file(path)
        self.check_all(self.custom_editor,'environment',{'UNITY_EXE':str(self.custom_editor)})

    def test_override_only_does_not_require_hub_installation(self):
        self.create_inert_file(self.custom_editor)
        self.check_all(self.custom_editor,'environment',{'UNITY_EXE':str(self.custom_editor)})

    def test_program_files_is_preferred_over_profile(self):
        self.create_inert_file(self.program_editor)
        self.create_inert_file(self.profile_editor)
        self.check_all(self.program_editor,'ProgramFiles')

    def test_user_profile_installation_is_found(self):
        self.create_inert_file(self.profile_editor)
        self.check_all(self.profile_editor,'USERPROFILE')

    def test_neither_location_reports_original_error_without_pausing(self):
        self.check_all(None)

    def test_invalid_override_falls_back_to_program_files(self):
        self.create_inert_file(self.program_editor)
        self.check_all(self.program_editor,'ProgramFiles',{'UNITY_EXE':str(self.custom_editor)})

    def test_invalid_override_falls_back_to_profile(self):
        self.create_inert_file(self.profile_editor)
        self.check_all(self.profile_editor,'USERPROFILE',{'UNITY_EXE':str(self.custom_editor)})

    def test_missing_override_and_defaults_fail(self):
        self.check_all(None,extra_env={'UNITY_EXE':str(self.custom_editor)})

    def test_directory_named_unity_exe_is_not_an_editor(self):
        self.program_editor.mkdir(parents=True)
        self.create_inert_file(self.profile_editor)
        self.check_all(self.profile_editor,'USERPROFILE',{'UNITY_EXE':str(self.program_editor)})

    def test_another_version_is_not_silently_selected(self):
        other = self.program_files/'Unity/Hub/Editor/6000.4.0f1/Editor/Unity.exe'
        self.create_inert_file(other)
        self.check_all(None)

    def test_missing_root_variables_do_not_search_current_directory(self):
        self.env.pop('ProgramFiles')
        self.env.pop('USERPROFILE')
        self.create_inert_file(self.workspace/RELATIVE_EDITOR)
        self.check_all(None)

    def test_spaces_shell_characters_and_delayed_expansion(self):
        custom = self.workspace/'Editor & tools (custom)!'/'Unity.exe'
        self.create_inert_file(custom)
        self.check_all(custom,'environment',{'UNITY_EXE':str(custom)},delayed=True)
        profile = self.workspace/'Profile & data (test)!'
        editor = profile/RELATIVE_EDITOR
        self.create_inert_file(editor)
        self.check_all(editor,'USERPROFILE',{'USERPROFILE':str(profile)},delayed=True)

    def test_non_ascii_profile_name(self):
        profile = self.workspace/'Profiles'/'사용자'
        editor = profile/RELATIVE_EDITOR
        self.create_inert_file(editor)
        self.check_all(editor,'USERPROFILE',{'USERPROFILE':str(profile)})


@unittest.skipUnless(os.name == 'nt' and CMD, 'Requires Windows path expansion')
class OtherToolPathTests(unittest.TestCase):
    def run_batch_assignments(self, name, variable, env_updates):
        # Execute only the exact SET/IF NOT DEFINED assignments, never the build script.
        source = (ROOT/name).read_text(encoding='utf-8').splitlines()
        prefix = 'if not defined '+variable+' set "'+variable+'='
        assignments = [line for line in source if line.startswith(prefix)]
        self.assertEqual(len(assignments),1)
        with tempfile.TemporaryDirectory(prefix='g1 assignment check ') as directory:
            probe = Path(directory)/'probe.bat'
            probe.write_text('@echo off\nsetlocal EnableExtensions DisableDelayedExpansion\n'
                             +assignments[0]+'\nset '+variable+'\nexit /b 0\n', encoding='utf-8', newline='\r\n')
            env = {k:v for k,v in os.environ.items() if k.upper() not in {variable.upper(),'PROGRAMFILES'}}
            env.update(env_updates)
            command = subprocess.list2cmdline([CMD])+' /d /u /v:off /c call "'+str(probe)+'"'
            result = subprocess.run(command,env=env,cwd=directory,capture_output=True,timeout=10)
            stdout = result.stdout.decode('utf-16-le',errors='replace')
            self.assertEqual(result.returncode,0,stdout+result.stderr.decode('utf-16-le',errors='replace'))
            return dict(line.split('=',1) for line in stdout.splitlines() if '=' in line)[variable]

    def test_adb_default_follows_program_files(self):
        actual = self.run_batch_assignments('tools/BUILD_AND_INSTALL_VR_APK.bat','ADB_EXE',
                                           {'ProgramFiles':r'D:\Portable Programs'})
        self.assertEqual(actual,r'D:\Portable Programs\Meta Quest Developer Hub\resources\bin\adb.exe')

    def test_adb_override_is_not_overwritten(self):
        expected = r'E:\Android Tools\adb.exe'
        actual = self.run_batch_assignments('tools/BUILD_AND_INSTALL_VR_APK.bat','ADB_EXE',
                                           {'ProgramFiles':r'D:\Portable Programs','ADB_EXE':expected})
        self.assertEqual(actual,expected)

    def test_vcvars_defaults_follow_program_files(self):
        for name in ('tools/TEST_MINK_CYCLE_CANDIDATE_OFFLINE.bat','tools/TEST_MINK_TORCH_OWNER_OFFLINE.bat'):
            with self.subTest(name=name):
                actual = self.run_batch_assignments(name,'VCVARS64',{'ProgramFiles':r'D:\Portable Programs'})
                self.assertEqual(actual,r'D:\Portable Programs\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvars64.bat')

    def test_vcvars_overrides_are_not_overwritten(self):
        expected = r'E:\Build Tools\vcvars64.bat'
        for name in ('tools/TEST_MINK_CYCLE_CANDIDATE_OFFLINE.bat','tools/TEST_MINK_TORCH_OWNER_OFFLINE.bat'):
            with self.subTest(name=name):
                actual = self.run_batch_assignments(name,'VCVARS64',
                    {'ProgramFiles':r'D:\Portable Programs','VCVARS64':expected})
                self.assertEqual(actual,expected)

    @unittest.skipUnless(shutil.which('powershell.exe'),'Requires Windows PowerShell')
    def test_powershell_vcvars_selection_only_and_full_script_syntax(self):
        name = ROOT/'experiments/twist2_right_arm_manual/VERIFY_OFFLINE.ps1'
        source = name.read_text(encoding='utf-8')
        prefix = source[:source.index('$root =')]
        self.assertNotIn('& cmd',prefix)
        self.assertNotIn('Push-Location',prefix)
        with tempfile.TemporaryDirectory(prefix='g1 PS resolver ') as directory:
            root = Path(directory)
            program_files = root/'Program Files'
            default = program_files/'Microsoft Visual Studio/18/Community/VC/Auxiliary/Build/vcvars64.bat'
            override = root/'Custom VS'/'vcvars64.bat'
            for path in (default,override):
                path.parent.mkdir(parents=True,exist_ok=True)
                path.write_text('Not executed.\n',encoding='ascii')
            probe = root/'resolve_only.ps1'
            probe.write_text(prefix+'\nWrite-Output $vcvars64\n',encoding='utf-8-sig')
            env = {k:v for k,v in os.environ.items() if k.upper() not in {'VCVARS64','PROGRAMFILES'}}
            env['ProgramFiles'] = str(program_files)
            args = [shutil.which('powershell.exe'),'-NoProfile','-ExecutionPolicy','Bypass','-File',str(probe)]
            for configured,expected in ((None,default),(str(override),override),(str(root/'missing.bat'),None)):
                current = dict(env)
                if configured is not None:
                    current['VCVARS64'] = configured
                result = subprocess.run(args,env=current,capture_output=True,text=True,timeout=15)
                if expected is None:
                    self.assertNotEqual(result.returncode,0)
                    self.assertIn('Set VCVARS64',result.stderr)
                else:
                    self.assertEqual(result.returncode,0,result.stderr)
                    self.assertEqual(result.stdout.strip(),str(expected))
            # Parse the complete changed PS1 but do not invoke any of its commands.
            parse = root/'parse_only.ps1'
            parse.write_text("$tokens=$null; $errors=$null; [void][System.Management.Automation.Language.Parser]::ParseFile($env:TEST_SCRIPT,[ref]$tokens,[ref]$errors); if($errors.Count){$errors | Out-String; exit 1}; Write-Output 'SYNTAX_OK'",encoding='utf-8')
            result = subprocess.run(args[:-1]+[str(parse)],env=dict(env,TEST_SCRIPT=str(name)),
                                    capture_output=True,text=True,timeout=15)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertIn('SYNTAX_OK',result.stdout)


if __name__ == '__main__':
    unittest.main()
