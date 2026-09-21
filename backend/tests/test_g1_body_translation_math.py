"""Execute production C# body-compensation math without Unity Play or hardware."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[2]
EDITORS=Path(os.environ.get('ProgramFiles',r'C:\Program Files'))/'Unity/Hub/Editor'
CANDIDATES=sorted(EDITORS.glob('*/Editor/Data'))
DATA=next((p for p in reversed(CANDIDATES) if (p/'MonoBleedingEdge/lib/mono/4.5/csc.exe').exists()),None)
HARNESS = 'static void Eq(Vector3 a,Vector3 b){if((a-b).magnitude>1e-5f)throw new Exception(a+" != "+b);}\nstatic Vector3 Step(Vector3 v,Vector3 h){return GetCommonBodyTranslationStep(v,h,.0005f,.85f,.55f,.012f);}\nstatic void Main(){\n// Hand alone, head alone: no false opposite target.\nEq(Step(new Vector3(.1f,0,0),Vector3.zero),Vector3.zero);\nEq(BoundBodyTranslation(Step(Vector3.zero,new Vector3(.1f,0,0)),new Vector3(.1f,0,0)),Vector3.zero);\n// Common body motion compensated, return missed by classifier still clears bias.\nVector3 move=new Vector3(.01f,0,0),e=Vector3.zero,h=Vector3.zero;\nfor(int i=0;i<20;i++){h+=move;e=BoundBodyTranslation(e+Step(move,move),h);}\nEq(e,h);Eq(CalculateBodyCompensatedTrackingDelta(h,Vector3.zero,e),Vector3.zero);\nfor(int i=0;i<20;i++){h-=move;e=BoundBodyTranslation(e+Step(Vector3.zero,-move),h);}\nEq(e,Vector3.zero);\n// Repetition cannot ratchet the offset; opposite/perpendicular candidates clear.\nfor(int i=0;i<1000;i++){e=BoundBodyTranslation(e+move,move);e=BoundBodyTranslation(e,Vector3.zero);}\nEq(e,Vector3.zero);Eq(BoundBodyTranslation(-move,move),Vector3.zero);\nEq(BoundBodyTranslation(new Vector3(0,.2f,0),move),Vector3.zero);\n// Recorded failure example: old24cm estimate bounded by current ~2cm head displacement.\nvar recorded=BoundBodyTranslation(new Vector3(.214f,-.083f,.066f),new Vector3(.019f,-.003f,.007f));\nif(recorded.magnitude>new Vector3(.019f,-.003f,.007f).magnitude+1e-6f)throw new Exception("bound");\nConsole.WriteLine("PASS: hand-only, head-only, common motion, missed return, 1000 cycles, direction bounds, recorded offset bound");\n}}\n'

@unittest.skipUnless(DATA is not None, 'Unity Mono compiler required')
class BodyTranslationTests(unittest.TestCase):
    def test_production_math(self):
        source=(ROOT/'Unity_G1_VR/Assets/G1Teleop/G1ExistingHandTargetBinder.cs').read_text(encoding='utf-8')
        methods=[]
        for name in ['BoundBodyTranslation','GetCommonBodyTranslationStep','CalculateBodyCompensatedTrackingDelta']:
            start=source.index('    public static Vector3 '+name+'(')
            end=source.index('{',start)+1;depth=1
            while depth:
                depth+=(source[end]=='{')-(source[end]=='}');end+=1
            methods.append(source[start:end])
        mono=str(DATA/'MonoBleedingEdge/bin/mono.exe')
        with tempfile.TemporaryDirectory() as directory:
            cs=Path(directory)/'BodyTests.cs';exe=cs.with_suffix('.exe')
            cs.write_text('using System;using UnityEngine;class BodyTests {\n'+'\n'.join(methods)+HARNESS)
            subprocess.run([mono,str(DATA/'MonoBleedingEdge/lib/mono/4.5/csc.exe'),'/noconfig','/nologo','/nostdlib+','/target:exe','/out:'+str(exe),'/reference:'+str(DATA/'NetStandard/ref/2.1.0/netstandard.dll'),'/reference:'+str(DATA/'Managed/UnityEngine/UnityEngine.CoreModule.dll'),str(cs)],check=True,capture_output=True,timeout=30)
            env=dict(os.environ,MONO_PATH=str(DATA/'Managed/UnityEngine'))
            result=subprocess.run([mono,str(exe)],env=env,capture_output=True,text=True,encoding="utf-8-sig",timeout=30,check=True)
            self.assertIn('PASS:',result.stdout)
