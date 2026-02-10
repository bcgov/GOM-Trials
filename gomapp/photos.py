import os
from kivy.clock import Clock
from pyobjus import autoclass
import hashlib
import uuid

UIImagePickerController = autoclass("UIImagePickerController")
UIApplication = autoclass("UIApplication")
ImagePickerDelegate = autoclass("ImagePickerDelegate")  # your Obj-C delegate
NSFileManager = autoclass("NSFileManager")

class IOSPhotoPicker:
    def __init__(self):
        self._poll_ev = None
        self._delegate = None
        self._on_done = None
        
    def get_ios_documents_dir(self):
        manager = NSFileManager.defaultManager()
        urls = manager.URLsForDirectory_inDomains_(9, 1)
        url0 = urls.objectAtIndex_(0)     # NSURL
        path_ns = url0.path               # NSString
        return path_ns.UTF8String()       # Python str


    def pick(self, source: str, on_done):
        """
        source: 'camera' or 'library'
        on_done: fn(result_path_or_none)
        """
        self._on_done = on_done

        picker = UIImagePickerController.alloc().init()
        if source == "camera":
            picker.sourceType = 1  # UIImagePickerControllerSourceTypeCamera
        else:
            picker.sourceType = 0  # Photo library

        delegate = ImagePickerDelegate.alloc().init()
        self._delegate = delegate
        picker.delegate = delegate

        app = UIApplication.sharedApplication()
        root = app.keyWindow.rootViewController()
        root.presentViewController_animated_completion_(picker, True, None)

        # start polling
        if self._poll_ev is None:
            self._poll_ev = Clock.schedule_interval(self._check_result, 0.25)

    def _check_result(self, dt):
        docs = self.get_ios_documents_dir()
        ipc_dir = os.path.join(docs, "gomapp_ipc")
        result_file = os.path.join(ipc_dir, "picker_result.txt")

        if not os.path.exists(result_file):
            return

        try:
            with open(result_file, "r") as f:
                result = f.read().strip()
        finally:
            try:
                os.remove(result_file)
            except OSError:
                pass

        # stop polling immediately
        if self._poll_ev is not None:
            self._poll_ev.cancel()
            self._poll_ev = None

        # free delegate ref
        self._delegate = None

        # normalize result
        if result == "__cancelled__" or result == "":
            result = None

        cb = self._on_done
        self._on_done = None
        if cb:
            cb(result)

def compute_sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()
