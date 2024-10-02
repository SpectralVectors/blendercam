"""CNC CAM 'autoupdate.py'

Classes to check for, download and install CNC CAM updates.
"""

import calendar
from datetime import date
import io
import json
import os
import pathlib
import re
import sys
from urllib.request import urlopen
import zipfile

import bpy
from bpy.props import StringProperty

from .version import __version__ as current_version


class UpdateChecker(bpy.types.Operator):
    """Check for Updates"""
    bl_idname = "render.cam_check_updates"
    bl_label = "Check for Updates in CNC CAM Plugin"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        addon_prefs = context.preferences.addons[__package__].preferences
        if bpy.app.background:
            return {"FINISHED"}
        last_update_check = addon_prefs.last_update_check
        today = date.today().toordinal()
        update_source = addon_prefs.update_source
        match = re.match(r"https://github.com/([^/]+/[^/]+)", update_source)
        if match:
            update_source = f"https://api.github.com/repos/{match.group(1)}/releases"

        print(f"Update Check: {update_source}")
        if update_source == "None" or len(update_source) == 0:
            return {'FINISHED'}

        addon_prefs.new_version_available = ""
        bpy.ops.wm.save_userpref()
        # get list of releases from github release
        if update_source.endswith("/releases"):
            with urlopen(update_source, timeout=2.0) as response:
                body = response.read().decode("UTF-8")
                # find the tag name
                release_list = json.loads(body)
                if len(release_list) > 0:
                    release = release_list[0]
                    tag = release["tag_name"]
                    print(f"Found Release: {tag}")
                    match = re.match(r".*(\d+)\.(\s*\d+)\.(\s*\d+)", tag)
                    if match:
                        version_num = tuple(map(int, match.groups()))
                        print(f"Found version: {version_num}")
                        addon_prefs.last_update_check = today

                        if version_num > current_version:
                            addon_prefs.new_version_available = ".".join(
                                [str(x) for x in version_num])
                        bpy.ops.wm.save_userpref()
        elif update_source.endswith("/commits"):
            with urlopen(update_source+"?per_page=1", timeout=2) as response:
                body = response.read().decode("UTF-8")
                # find the tag name
                commit_list = json.loads(body)
                commit_sha = commit_list[0]['sha']
                commit_date = commit_list[0]['commit']['author']['date']
                if addon_prefs.last_commit_hash != commit_sha:
                    addon_prefs.new_version_available = commit_date
                    bpy.ops.wm.save_userpref()
        return {'FINISHED'}


class Updater(bpy.types.Operator):
    """Update to Newer Version if Possible"""
    bl_idname = "render.cam_update_now"
    bl_label = "Update"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        addon_prefs = context.preferences.addons[__package__].preferences
        print("Update Check")
        last_update_check = addon_prefs.last_update_check
        today = date.today().toordinal()
        update_source = addon_prefs.update_source
        if update_source == "None" or len(update_source) == 0:
            return {'FINISHED'}
        match = re.match(r"https://github.com/([^/]+/[^/]+)", update_source)
        if match:
            update_source = f"https://api.github.com/repos/{match.group(1)}/releases"

        # get list of releases from github release
        if update_source.endswith("/releases"):
            with urlopen(update_source, timeout=2) as response:
                body = response.read().decode("UTF-8")
                # find the tag name
                release_list = json.loads(body)
                if len(release_list) > 0:
                    release = release_list[0]
                    tag = release["tag_name"]
                    print(f"Found Release: {tag}")
                    match = re.match(r".*(\d+)\.(\s*\d+)\.(\s*\d+)", tag)
                    if match:
                        version_num = tuple(map(int, match.groups()))
                        print(f"Found version: {version_num}")
                        addon_prefs.last_update_check = today
                        bpy.ops.wm.save_userpref()

                        if version_num > current_version:
                            print("Version Is Newer, Downloading Source")
                            zip_url = release["zipball_url"]
                            self.install_zip_from_url(zip_url)
                            return {'FINISHED'}
        elif update_source.endswith("/commits"):
            with urlopen(update_source+"?per_page=1", timeout=2) as response:
                body = response.read().decode("UTF-8")
                # find the tag name
                commit_list = json.loads(body)
                commit_sha = commit_list[0]['sha']
                if addon_prefs.last_commit_hash != commit_sha:
                    # get zipball from this commit
                    zip_url = update_source.replace(
                        "/commits", f"/zipball/{commit_sha}")
                    self.install_zip_from_url(zip_url)
                    addon_prefs.last_commit_hash = commit_sha
                    bpy.ops.wm.save_userpref()
        return {'FINISHED'}

    def install_zip_from_url(self, zip_url):
        addon_prefs = bpy.context.preferences.addons[__package__].preferences
        with urlopen(zip_url) as zip_response:
            zip_body = zip_response.read()
            buffer = io.BytesIO(zip_body)
            zf = zipfile.ZipFile(buffer, mode='r')
            files = zf.infolist()
            cam_addon_path = pathlib.Path(__file__).parent
            for fileinfo in files:
                filename = fileinfo.filename
                if fileinfo.is_dir() == False:
                    path_pos = filename.replace("\\", "/").find("/scripts/addons/cam/")
                    if path_pos != -1:
                        relative_path = filename[path_pos + len("/scripts/addons/cam/"):]
                        out_path = cam_addon_path / relative_path
                        print(out_path)
                        # check folder exists
                        out_path.parent.mkdir(parents=True, exist_ok=True)
                        with zf.open(filename, "r") as in_file, open(out_path, "wb") as out_file:
                            time_struct = (*fileinfo.date_time, 0, 0, 0)
                            mtime = calendar.timegm(time_struct)
                            out_file.write(in_file.read())
                        os.utime(out_path, times=(mtime, mtime))
                        # TODO: check for newer times
                        # TODO: what about if a file is deleted...
            # updated everything, now mark as updated and reload scripts
            addon_prefs.just_updated = True
            addon_prefs.new_version_available = ""
            bpy.ops.wm.save_userpref()
            # unload ourself from python module system
            delete_list = []
            for m in sys.modules.keys():
                if m.startswith("cam.") or m == 'cam':
                    delete_list.append(m)
            for d in delete_list:
                del sys.modules[d]
            bpy.ops.script.reload()


class UpdateSourceOperator(bpy.types.Operator):
    bl_idname = "render.cam_set_update_source"
    bl_label = "Set CNC CAM Update Source"

    new_source: StringProperty(
        default='',
    )

    def execute(self, context):
        context.preferences.addons[__package__].preferences.update_source = self.new_source
        bpy.ops.wm.save_userpref()
        return {'FINISHED'}
