"""Folder visibility and a timed verification gate. No encryption."""
import ctypes
import os
from pathlib import Path

HIDDEN, NORMAL = 2, 128

def attributes_with_hidden(attributes, hidden):
    value = attributes | HIDDEN if hidden else attributes & ~HIDDEN
    if value & ~NORMAL:
        value &= ~NORMAL
    return value or NORMAL

def windows_api():
    if os.name != 'nt':
        raise RuntimeError('This application requires Windows 11.')
    api = ctypes.WinDLL('kernel32', use_last_error=True)
    api.GetFileAttributesW.argtypes = [ctypes.c_wchar_p]
    api.GetFileAttributesW.restype = ctypes.c_uint32
    api.SetFileAttributesW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32]
    api.SetFileAttributesW.restype = ctypes.c_int
    return api

class Locker:
    def __init__(self, project):
        self.path = Path(project).resolve().parent / 'Locker'
        fresh = not self.path.exists()
        if self.path.is_symlink():
            raise RuntimeError('Locker must be a real folder, not a link.')
        self.path.mkdir(exist_ok=True)
        if self.path.resolve() != self.path:
            raise RuntimeError('Locker must not be a junction or redirected folder.')
        self.api = windows_api()
        if fresh:
            self.hide()

    def attributes(self):
        value = self.api.GetFileAttributesW(str(self.path))
        if value == 0xFFFFFFFF:
            raise ctypes.WinError(ctypes.get_last_error())
        return value

    @property
    def hidden(self):
        return bool(self.attributes() & HIDDEN)

    def visibility(self, hidden):
        value = attributes_with_hidden(self.attributes(), hidden)
        if not self.api.SetFileAttributesW(str(self.path), value):
            raise ctypes.WinError(ctypes.get_last_error())
        if self.hidden != hidden:
            raise RuntimeError('Folder visibility could not be verified.')

    def hide(self):
        self.visibility(True)

    def open(self):
        self.visibility(False)
        try:
            os.startfile(str(self.path))
        except Exception:
            self.hide()
            raise

class Gate:
    """Requires eight matches spanning at least 1.2 seconds within 30 seconds."""
    def __init__(self, started, required=8, duration=1.2, timeout=30):
        self.started, self.required, self.duration, self.timeout = started, required, duration, timeout
        self.count, self.first = 0, None

    def expired(self, now):
        return now - self.started >= self.timeout

    def update(self, accepted, now):
        if not accepted or self.expired(now):
            self.count, self.first = 0, None
            return False
        if self.first is None:
            self.first = now
        self.count += 1
        return self.count >= self.required and now - self.first >= self.duration

class Folder:
    """Operate on an existing selected directory; never create it implicitly."""
    def __init__(self,path):
        self.path=Path(path).absolute()
        if not self.path.is_dir() or self.path.is_symlink() or self.path.resolve()!=self.path:
            raise ValueError(f'Folder is missing or redirected: {self.path}')
        self.api=windows_api()

    attributes=Locker.attributes
    hidden=Locker.hidden
    visibility=Locker.visibility

def validate_folder(path,project):
    path=Path(path).absolute()
    resolved=path.resolve()
    project=Path(project).resolve()
    if not path.is_dir() or path.is_symlink() or resolved!=path:
        raise ValueError('Choose an existing real folder, not a shortcut or junction.')
    if path==Path(path.anchor):
        raise ValueError('A drive root cannot be selected.')
    if resolved==project or resolved in project.parents:
        raise ValueError('Do not select the application folder or a parent containing it.')
    # Avoid selecting operating-system directories; normal user folders remain allowed.
    for key in ('SystemRoot','ProgramFiles','ProgramFiles(x86)','ProgramData'):
        value=os.environ.get(key)
        if value:
            protected=Path(value).resolve()
            if resolved==protected or protected in resolved.parents:
                raise ValueError('Choose a personal folder, outside Windows/program system directories.')
    return str(resolved)

def prepare_jobs(jobs,project):
    validated=[]
    seen=set()
    for path,hidden in jobs:
        path=validate_folder(path,project)
        key=os.path.normcase(path)
        if key in seen: raise ValueError('Duplicate folder in operation.')
        seen.add(key);validated.append((path,bool(hidden)))
    if not validated: raise ValueError('Select at least one folder.')
    for parent,hide_parent in validated:
        for child,hide_child in validated:
            if hide_parent and not hide_child and Path(parent) in Path(child).parents:
                raise ValueError('Cannot reveal a child while hiding its selected parent in the same operation.')
    return tuple(validated)

def apply_batch(jobs,factory=Folder):
    """Preflight all entries; report individual outcomes without claiming full success."""
    entries=[(factory(path),hidden) for path,hidden in jobs]
    outcomes=[]
    for folder,hidden in entries:
        try:
            folder.visibility(hidden)
            outcomes.append((str(folder.path),True,''))
        except Exception as exc:
            outcomes.append((str(folder.path),False,str(exc)))
    return outcomes

class VerifiedAction:
    """One-shot immutable operation. Cancel discards it; matching alone does not execute it."""
    def __init__(self,owner,started,jobs=(),purpose='folders'):
        self.owner=owner
        self.jobs=tuple((str(path),bool(hidden)) for path,hidden in jobs)
        self.purpose=purpose
        self.gate=Gate(started)
        self.active=True

    def cancel(self):
        self.active=False

    def consume(self,name,face_count,now):
        if not self.active: return False
        accepted=face_count==1 and name==self.owner
        if self.gate.update(accepted,now):
            self.active=False
            return True
        return False
