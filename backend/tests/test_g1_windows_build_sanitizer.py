"""Compile actual C# sanitizer helpers without Unity or any robot runtime."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
CSC=Path(os.environ.get('WINDIR',r'C:\Windows'))/'Microsoft.NET/Framework64/v4.0.30319/csc.exe'

@unittest.skipUnless(CSC.is_file(), 'requires installed Windows .NET Framework C# compiler')
class SanitizerTests(unittest.TestCase):
    def test_actual_csharp_helpers(self):
        text=(ROOT/'Unity_G1_VR/Assets/Editor/G1VRBuild.cs').read_text()
        helpers=text[text.index('    private static string ReadYamlValue('):text.rfind('\n}')]
        main=r'''
public static void Main() {
 byte[] one=Encoding.UTF8.GetBytes("prefix dummy-token suffix");
 ReplaceUniqueUtf8Value(one,"dummy-token","fixture");
 if(CountOccurrences(one,Encoding.UTF8.GetBytes("dummy-token"))!=0) throw new Exception("token remained");
 int rejected=0;
 foreach(string value in new[]{"missing","repeat repeat"}) {
  try {ReplaceUniqueUtf8Value(Encoding.UTF8.GetBytes(value),"repeat","fixture");}
  catch(InvalidDataException) {rejected++;}
 }
 if(rejected!=2) throw new Exception("count guards relaxed");
 byte[] empty=Encoding.UTF8.GetBytes("untouched"); ReplaceUniqueUtf8Value(empty,"","fixture");
 if(Encoding.UTF8.GetString(empty)!="untouched") throw new Exception("empty mutation");
 if(ReadYamlValue("  serverAddress: \n  nextField: value\n","serverAddress")!="") throw new Exception("YAML boundary");
 byte[] multi=Encoding.UTF8.GetBytes("prefix 테스트 suffix"); ReplaceUniqueUtf8Value(multi,"테스트","fixture");
 if(CountOccurrences(multi,Encoding.UTF8.GetBytes("테스트"))!=0) throw new Exception("UTF8 value remained");
 Console.WriteLine("PASS: real C# sanitizer helpers");
}
'''
        source='using System;using System.IO;using System.Text;using System.Text.RegularExpressions;public static class Fixture {\n'+main+helpers+'\n}'
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'fixture.cs'; path.write_text(source,encoding='utf-8')
            exe=Path(directory)/'fixture.exe'
            compiled=subprocess.run([str(CSC),'/nologo','/out:'+str(exe),str(path)],capture_output=True,timeout=30)
            self.assertEqual(compiled.returncode,0,compiled.stdout.decode(errors='replace'))
            result=subprocess.run([str(exe)],capture_output=True,timeout=15)
            self.assertEqual(result.returncode,0,result.stdout.decode(errors='replace'))
            self.assertIn(b'PASS: real C# sanitizer helpers',result.stdout)

if __name__=='__main__': unittest.main()
