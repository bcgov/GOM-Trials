# file_picker.py
#
# iOS-only Files.app picker for Kivy using UIDocumentPickerViewController via pyobjus.
# - Opens the *Files* picker (not Photos)
# - Filters by extension (e.g. .mbtiles / .tif)
# - Copies the selected file into your app sandbox (App.user_data_dir/subdir/)
# - Calls your callback with a list of local sandbox paths
#
# Usage (in RootWidget):
#   from file_picker import pick_files
#   pick_files(exts=(".mbtiles",), callback=self._on_mbtiles, subdir="mbtiles")

import shutil
from pathlib import Path

from kivy.app import App
from kivy.clock import mainthread

from pyobjus import autoclass, protocol, objc_str
from pyobjus.dylib_manager import load_framework

# Frameworks
load_framework("/System/Library/Frameworks/UIKit.framework")
load_framework("/System/Library/Frameworks/Foundation.framework")

UIApplication = autoclass("UIApplication")
UIDocumentPickerViewController = autoclass("UIDocumentPickerViewController")
NSArray = autoclass("NSArray")
NSData = autoclass("NSData")


# Keep references so delegate/picker don't get GC'd while visible
_picker_ref = None
_delegate_ref = None


def _objc_get(obj, name):
    """
    pyobjus sometimes exposes selectors as callables (foo()) and sometimes as
    properties (foo). This handles both.
    """
    val = getattr(obj, name, None)
    if val is None:
        return None
    try:
        return val() if callable(val) else val
    except TypeError:
        return val
        
def _nsstr(x) -> str:
    """Convert NSString/NSPathStore2/etc to a Python str safely."""
    if x is None:
        return ""
    try:
        # NSString.UTF8String -> C string pointer wrapper; str() gives text
        s = _objc_get(x, "UTF8String")
        if s is not None:
            return str(s)
    except Exception:
        pass
    # Fallback: description usually exists
    try:
        d = _objc_get(x, "description")
        if d is not None:
            return str(d)
    except Exception:
        pass
    return str(x)


def _objc_call(obj, *names, args=()):
    """
    Call the first selector name that exists on obj.
    Useful because pyobjus name-mangling differs (e.g. presentViewController_animated_completion_).
    """
    last_err = None
    for nm in names:
        try:
            fn = getattr(obj, nm)
            return fn(*args)
        except Exception as e:
            last_err = e
    if last_err:
        raise last_err
    raise AttributeError(f"No selector found on {obj} for any of: {names}")


def _top_view_controller():
    """
    Find the topmost UIViewController to present from.
    Works with Kivy's SDL_uikitviewcontroller.
    """
    app = UIApplication.sharedApplication()

    window = _objc_get(app, "keyWindow")  # sometimes callable, sometimes property
    if window is None:
        windows = _objc_get(app, "windows")
        if windows is not None:
            window = _objc_get(windows, "firstObject")

    if window is None:
        raise RuntimeError("Could not obtain iOS window (keyWindow/windows).")

    vc = _objc_get(window, "rootViewController")
    if vc is None:
        raise RuntimeError("Could not obtain rootViewController from window.")

    # Walk to topmost presented VC
    while True:
        presented = _objc_get(vc, "presentedViewController")
        if presented is None:
            break
        vc = presented

    return vc

def _copy_to_app_storage_from_url(nsurl, subdir: str) -> str:
    app = App.get_running_app()
    dst_dir = Path(app.user_data_dir) / subdir
    dst_dir.mkdir(parents=True, exist_ok=True)

    name = str(_objc_get(nsurl, "lastPathComponent")) or "imported_file"
    dst = dst_dir / name

    data = NSData.dataWithContentsOfURL_(nsurl)
    if data is None:
        raise RuntimeError("NSData.dataWithContentsOfURL_ returned None (provider file not readable)")

    ok = data.writeToFile_atomically_(str(dst), True)
    if not ok:
        raise RuntimeError("Failed to write imported file to app storage")

    return str(dst)


def _copy_to_app_storage(src_path: str, subdir: str) -> str:
    """
    Copy src_path into App.user_data_dir/subdir and return the destination path.
    """
    app = App.get_running_app()
    dst_dir = Path(app.user_data_dir) / subdir
    dst_dir.mkdir(parents=True, exist_ok=True)

    dst = dst_dir / Path(src_path).name
    shutil.copy2(src_path, dst)
    return str(dst)


class IOSFilesChooser:
    """
    Instance-based picker so we can store callback/ext filters safely.
    """

    def __init__(self):
        self._on_selection = None
        self._exts = ()
        self._subdir = "imports"

    @mainthread
    def open_file(self, *, exts, on_selection, subdir="imports", allow_multiple=False):
        """
        exts: tuple like (".mbtiles",) or (".tif", ".tiff")
        on_selection: callback(list_of_local_paths)
        """
        global _picker_ref, _delegate_ref

        self._on_selection = on_selection
        self._exts = tuple(e.lower() for e in exts)
        self._subdir = subdir

        # Ask for broad document type so iOS shows Files; we filter extensions ourselves.
        doc_types = NSArray.arrayWithObject_(objc_str("public.data"))
        mode_import = 0  # UIDocumentPickerModeImport

        picker = UIDocumentPickerViewController.alloc().initWithDocumentTypes_inMode_(doc_types, mode_import)

        # Multiple selection (optional)
        try:
            picker.setAllowsMultipleSelection_(bool(allow_multiple))
        except Exception:
            pass

        picker.setDelegate_(self)

        vc = _top_view_controller()

        # Correct selector spelling for pyobjus:
        # presentViewController:animated:completion: -> presentViewController_animated_completion_
        _objc_call(
            vc,
            "presentViewController_animated_completion_",
            "presentViewControllerAnimated_completion_",  # fallback if your build ever expects it
            args=(picker, True, None),
        )

        # Keep alive
        _picker_ref = picker
        _delegate_ref = self

    # Delegate callbacks (older pyobjus: decorate the METHODS with @protocol)
    @protocol("UIDocumentPickerDelegate")
    def documentPicker_didPickDocumentsAtURLs_(self, picker, urls):
        picked = []
        try:
            n = urls.count()
            for i in range(n):
                url = urls.objectAtIndex_(i)

                # Use filename for filtering (more reliable than full path for provider URLs)
                name_obj = _objc_get(url, "lastPathComponent")
                name = _nsstr(name_obj)
                print("📄 Picked name:", name)

                if not name:
                    print("⚠️ No filename from URL; skipping")
                    continue

                name_l = name.lower()
                if self._exts and not name_l.endswith(self._exts):
                    print("⚠️ Skipping due to extension filter:", self._exts)
                    continue

                # Security scope (safe to attempt)
                try:
                    _objc_call(url, "startAccessingSecurityScopedResource", args=())
                except Exception as e:
                    print("⚠️ startAccessingSecurityScopedResource failed:", e)

                try:
                    # Copy via NSData from NSURL (works with File Provider / iCloud)
                    local = _copy_to_app_storage_from_url(url, self._subdir)
                    print("✅ Copied to:", local)
                    picked.append(local)
                except Exception as e:
                    print("❌ Copy failed:", e)

                try:
                    _objc_call(url, "stopAccessingSecurityScopedResource", args=())
                except Exception as e:
                    print("⚠️ stopAccessingSecurityScopedResource failed:", e)

        except Exception as e:
            print("⚠️ documentPicker_didPickDocumentsAtURLs_ error:", e)

        self._finish(picker, picked)

    @protocol("UIDocumentPickerDelegate")
    def documentPickerWasCancelled_(self, picker):
        self._finish(picker, [])

    @mainthread
    def _finish(self, picker, selection):
        global _picker_ref, _delegate_ref

        # dismissViewControllerAnimated:completion: -> dismissViewControllerAnimated_completion_
        try:
            _objc_call(
                picker,
                "dismissViewControllerAnimated_completion_",
                args=(True, None),
            )
        except Exception:
            # Not fatal if dismissal fails
            pass

        try:
            if self._on_selection:
                self._on_selection(selection)
        finally:
            _picker_ref = None
            _delegate_ref = None


# Convenience one-liner (matches your earlier usage style)
_files_chooser_singleton = IOSFilesChooser()


def pick_files(exts, callback, subdir="imports", allow_multiple=False):
    """
    Convenience function so callers don't need to manage IOSFilesChooser instances.
    callback receives list of local sandbox paths.
    """
    _files_chooser_singleton.open_file(
        exts=exts,
        on_selection=callback,
        subdir=subdir,
        allow_multiple=allow_multiple,
    )

