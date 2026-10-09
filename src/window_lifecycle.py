"""Only announce readiness after the window has been mapped by the event loop."""
import time

def show_and_confirm(root,on_ready=lambda:None,on_error=None,timeout=10):
    deadline=time.monotonic()+timeout
    def check():
        if not root.winfo_exists():return
        root.deiconify();root.lift();root.update_idletasks()
        if root.state()!='withdrawn' and root.winfo_viewable():
            print('[startup] Window mapped and visible',flush=True)
            on_ready();return
        if time.monotonic()>=deadline:
            message='The main window could not be displayed.'
            if on_error:on_error(message)
            else:raise RuntimeError(message)
            return
        root.after(100,check)
    root.after(50,check)
