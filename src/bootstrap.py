"""Windows first-run bootstrap; no third-party imports required."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
import uuid
import traceback

APP_FILES=('window_lifecycle.py','runtime_entry.py','instance.py','ui.py','app.py','database.py','vision.py','locker.py','strings.py','requirements.txt','LICENSE','README.md','INSTALLATION.md')
PYTHON_URL='https://www.python.org/ftp/python/3.10.11/python-3.10.11-amd64.exe'
PYTHON_SHA256='d8dede5005564b408ba50317108b765ed9c3c510342a598f9fd42681cbe0648b'
MODEL_NAMES=('face_detection_yunet_2023mar.onnx','face_recognition_sface_2021dec.onnx')


def install_root():
    if os.name!='nt':raise RuntimeError('The launcher requires Windows 11 x64.')
    return Path(os.environ['LOCALAPPDATA'])/'FaceLocker'


def payload_root():
    if getattr(sys,'frozen',False):return Path(sys._MEIPASS)/'payload'
    return Path(__file__).resolve().parent.parent


def payload_file(payload,name):
    """Read flat frozen/test payloads or the organized source checkout."""
    payload=Path(payload)
    direct=payload/name
    if direct.is_file():return direct
    folder='src' if name.endswith('.py') else 'requirements' if name=='requirements.txt' else 'docs'
    return payload/folder/name


def external_env(root):
    env=os.environ.copy()
    for key in list(env):
        if key in ('PYTHONHOME','PYTHONPATH','TCL_LIBRARY','TK_LIBRARY','TCLLIBPATH','_MEIPASS2') or key.startswith('_PYI_'):
            env.pop(key,None)
    bundle=getattr(sys,'_MEIPASS',None)
    if bundle:
        folder=Path(bundle).resolve()
        env['PATH']=os.pathsep.join(entry for entry in env.get('PATH','').split(os.pathsep)
                                   if entry and not Path(entry).resolve().is_relative_to(folder))
    env['FACELOCKER_HOME']=str(root)
    env['PYTHONIOENCODING']='utf-8'
    env['PYTHONUTF8']='1'
    return env


def fingerprint(payload):
    digest=hashlib.sha256()
    for name in APP_FILES:
        digest.update(name.encode());digest.update(payload_file(payload,name).read_bytes())
    return digest.hexdigest()


def deploy_payload(payload,root):
    target=Path(root)/'app';target.mkdir(parents=True,exist_ok=True)
    for name in APP_FILES:
        source=payload_file(payload,name)
        if not source.is_file():raise FileNotFoundError(f'Missing application payload: {name}')
        destination=target/name
        if destination.exists() and destination.read_bytes()==source.read_bytes():continue
        temporary=destination.with_suffix(destination.suffix+'.tmp')
        shutil.copyfile(source,temporary);os.replace(temporary,destination)
    return target


def migrate_adjacent_data(source,root):
    """Copy legacy enrollments only into a fresh managed install; never overwrite."""
    source,root=Path(source),Path(root)
    if (root/'data'/'state.json').exists() or (root/'data'/'people.json').exists():return False
    if source.resolve()==root.resolve():return False
    for name in ('state.json','people.json'):
        original=source/'data'/name
        if original.is_file():
            json.loads(original.read_text(encoding='utf-8'))
            (root/'data').mkdir(parents=True,exist_ok=True)
            shutil.copy2(original,root/'data'/name)
            config=source/'config.json'
            if name=='people.json' and config.is_file() and not (root/'config.json').exists():
                shutil.copy2(config,root/'config.json')
            return True
    return False


class Installer:
    def __init__(self,root,payload,emit=lambda key,**values:None):
        self.root=Path(root);self.payload=Path(payload);self.emit=emit
        self.root.mkdir(parents=True,exist_ok=True)
        (self.root/'logs').mkdir(exist_ok=True)
        self.log_path=self.root/'logs'/'setup.log'
        self.env=external_env(self.root)
        self.python=self.root/'.venv'/'Scripts'/'python.exe'
        self.app_dir=self.root/'app'
        self.ready=self.root/'setup-ready.json'

    def command(self,args,allowed=(0,),timeout=1200):
        # Arguments are always lists; paths with spaces/Unicode are not shell code.
        flags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0
        with self.log_path.open('a',encoding='utf-8') as log:
            log.write(f'\n[{time.ctime()}] {subprocess.list2cmdline([str(a) for a in args])}\n');log.flush()
            result=subprocess.run([str(a) for a in args],cwd=self.root,env=self.env,
                                  stdout=log,stderr=log,creationflags=flags,timeout=timeout)
        if result.returncode not in allowed:
            raise RuntimeError(f'Command failed (exit {result.returncode}). See setup.log.')
        return result.returncode

    def probe(self,python,code):
        try:self.command([python,'-I','-c',code],timeout=60);return True
        except (OSError,RuntimeError,subprocess.TimeoutExpired):return False

    def python_ok(self,path):
        return Path(path).is_file() and self.probe(path,
            'import sys,struct,tkinter,venv,ensurepip; assert sys.version_info[:2]==(3,10) and struct.calcsize("P")==8')

    def find_python(self):
        private=self.root/'runtime'/'python.exe'
        if self.python_ok(private):return private
        # Prefer a compatible existing full Python to avoid altering an existing install.
        try:
            flags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0
            result=subprocess.run(['py','-3.10','-c','import sys;print(sys.executable)'],
                                  env=self.env,capture_output=True,text=True,creationflags=flags,timeout=30)
            candidate=Path(result.stdout.strip())
            if result.returncode==0 and self.python_ok(candidate):return candidate
        except (OSError,subprocess.TimeoutExpired):pass
        candidate=Path(sys.executable)
        if not getattr(sys,'frozen',False) and self.python_ok(candidate):return candidate
        return None

    def download_python(self):
        cache=self.root/'downloads';cache.mkdir(exist_ok=True)
        target=cache/'python-3.10.11-amd64.exe'
        if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest()==PYTHON_SHA256:return target
        temporary=target.with_suffix('.part')
        try:
            with urllib.request.urlopen(PYTHON_URL,timeout=120) as response,temporary.open('wb') as output:
                size=int(response.headers.get('Content-Length',0));received=0;last=-1
                while chunk:=response.read(1024*1024):
                    output.write(chunk);received+=len(chunk)
                    percent=int(received*100/size) if size else 0
                    if percent!=last:self.emit('boot_download',percent=percent);last=percent
            if hashlib.sha256(temporary.read_bytes()).hexdigest()!=PYTHON_SHA256:
                raise RuntimeError('Python installer checksum mismatch. No installer was executed.')
            os.replace(temporary,target)
            return target
        finally:temporary.unlink(missing_ok=True)

    def install_python(self):
        self.emit('boot_python')
        python=self.find_python()
        if python:return python
        installer=self.download_python()
        self.emit('boot_install')
        target=self.root/'runtime'
        if target.exists():
            target.rename(self.root/f'runtime.incomplete-{time.time_ns()}')
        result=self.command([installer,'/quiet','InstallAllUsers=0',f'TargetDir={target}',
            'Include_launcher=0','InstallLauncherAllUsers=0','Include_test=0','Include_doc=0',
            'Include_pip=1','Include_tcltk=1','PrependPath=0','Shortcuts=0','AssociateFiles=0'],allowed=(0,3010))
        python=target/'python.exe'
        if not self.python_ok(python):
            suffix=' Restart Windows and retry.' if result==3010 else ''
            raise RuntimeError('Python setup did not provide the required interpreter.'+suffix)
        return python

    def dependencies_ok(self):
        return self.python.is_file() and self.probe(self.python,
            'import cv2,numpy,tkinter,customtkinter,PIL;'
            'import sys,struct;assert sys.version_info[:2]==(3,10) and struct.calcsize("P")==8;'
            'assert cv2.__version__=="4.10.0" and numpy.__version__=="1.26.4"')

    def models_ok(self):
        if not all((self.root/'models'/name).is_file() for name in MODEL_NAMES):return False
        detection=str(self.root/'models'/MODEL_NAMES[0]);recognition=str(self.root/'models'/MODEL_NAMES[1])
        code=f'import cv2;cv2.FaceDetectorYN.create({detection!r},"",(640,480));cv2.FaceRecognizerSF.create({recognition!r},"")'
        return self.probe(self.python,code)

    def marked_ready(self,digest):
        try:return json.loads(self.ready.read_text(encoding='utf-8')).get('fingerprint')==digest
        except (OSError,ValueError):return False

    def ensure(self):
        self.emit('boot_payload');self.app_dir=deploy_payload(self.payload,self.root)
        digest=fingerprint(self.payload)
        dependencies=self.dependencies_ok()
        requirements_hash=hashlib.sha256(payload_file(self.payload,'requirements.txt').read_bytes()).hexdigest()
        try:requirements_changed=json.loads(self.ready.read_text(encoding='utf-8')).get('requirements_hash')!=requirements_hash
        except (OSError,ValueError):requirements_changed=True
        if dependencies and self.marked_ready(digest) and self.models_ok():return self.python
        self.ready.unlink(missing_ok=True)
        if not self.python_ok(self.python):
            base=self.install_python();self.emit('boot_env')
            venv=self.root/'.venv'
            if venv.exists():
                backup=self.root/f'.venv.incomplete-{time.time_ns()}'
                venv.rename(backup)  # Keep a broken previous environment for recovery.
            self.command([base,'-m','venv',str(venv)])
        if not dependencies or requirements_changed:
            self.emit('boot_packages')
            self.command([self.python,'-m','pip','install','--disable-pip-version-check','--only-binary=:all:',
                          '-r',str(self.app_dir/'requirements.txt')])
        if not self.dependencies_ok():raise RuntimeError('Dependency verification failed.')
        if not self.models_ok():
            self.emit('boot_models')
            self.command([self.python,str(self.app_dir/'app.py'),'--setup'])
        if not self.models_ok():raise RuntimeError('Face model verification failed.')
        temporary=self.ready.with_suffix('.tmp')
        temporary.write_text(json.dumps({'fingerprint':digest,'requirements_hash':requirements_hash,'schema':2}),encoding='utf-8')
        os.replace(temporary,self.ready)
        return self.python

    def record_error(self):
        with self.log_path.open('a',encoding='utf-8') as log:
            log.write('\n'+traceback.format_exc())

    def launch(self,startup_timeout=45):
        self.emit('boot_launch')
        ready=self.root/'logs'/f'window-ready-{uuid.uuid4().hex}.json'
        env=self.env.copy();env['FACELOCKER_READY_FILE']=str(ready)
        flags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0
        with self.log_path.open('a',encoding='utf-8') as log:
            entry=self.app_dir/'runtime_entry.py'
            script=entry if entry.is_file() else self.app_dir/'app.py'
            command=[str(self.python),'-u','-X','faulthandler',str(script)]
            log.write(f'\n[{time.ctime()}] {subprocess.list2cmdline(command)}\n');log.flush()
            process=subprocess.Popen(command,cwd=self.root,
                                     env=env,stdout=log,stderr=log,creationflags=flags)
            try:
                deadline=time.monotonic()+startup_timeout
                while not ready.is_file():
                    result=process.poll()
                    if result is not None:
                        raise RuntimeError(f'FaceLocker exited before its window was ready (exit {result}). See setup.log.')
                    if time.monotonic()>=deadline:
                        raise RuntimeError('The FaceLocker window did not become ready. See setup.log and retry.')
                    time.sleep(.1)
                self.emit('boot_window_ready')
                result=process.wait()
                if result!=0:raise RuntimeError(f'FaceLocker stopped (exit {result}). See setup.log.')
            finally:
                if process.poll() is None:
                    process.terminate()
                    try:process.wait(timeout=5)
                    except subprocess.TimeoutExpired:process.kill();process.wait()
                ready.unlink(missing_ok=True)

