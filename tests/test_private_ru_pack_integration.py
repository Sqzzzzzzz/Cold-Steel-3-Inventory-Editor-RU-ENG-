"""A user-installed translation pack must not be misidentified as English."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import tkinter as tk

from app import Editor
from catalog_core import load_catalog_json
from game_scan import config_dir

class ExternalPackTests(unittest.TestCase):
    def build_editor(self):
        try:
            editor=Editor()
        except tk.TclError:
            self.skipTest('Graphical display unavailable')
        for job in editor._startup_jobs:
            editor.after_cancel(job)
        return editor

    def test_source_without_pack_displays_en_marker(self):
        with tempfile.TemporaryDirectory() as path, patch.dict(os.environ,{'APPDATA':path}):
            root=config_dir(); root.mkdir(parents=True)
            records={'items':[{'id':3574,'name':'EP 1','description':'◆',
                               'category':'quartz_normal','kind':'quartz','element':'mirage'}]}
            (root/'catalog_scanned.json').write_text(json.dumps(records),encoding='utf8')
            (root/'catalog_english.json').write_text(json.dumps(records),encoding='utf8')
            editor=self.build_editor()
            try:
                self.assertEqual(editor._get_name(3574),'[EN] EP 1')
            finally: editor.destroy()

    def test_private_pack_removes_marker_and_preserves_english(self):
        with tempfile.TemporaryDirectory() as path, patch.dict(os.environ,{'APPDATA':path}):
            root=config_dir(); root.mkdir(parents=True)
            english={'items':[
                {'id':3574,'name':'EP 1','description':'◆','kind':'quartz','element':'mirage','category':'quartz_normal'},
                {'id':3807,'name':'Faculty Swimsuit - Juna','description':'A swimsuit that looks just like the one Aurelia wears.',
                 'kind':'item','category':'costume'}]}
            overrides={'items':[
                {'id':3574,'name':'EP 1','description':'◆','category':'quartz_normal','kind':'quartz','element':'mirage','_locale':'ru'},
                {'id':3807,'name':'Купальник преподавателя — Юна',
                 'description':'Купальник, похожий на купальник Аурелии.',
                 'kind':'item','category':'costume','_locale':'ru'}]}
            (root/'catalog_scanned.json').write_text(json.dumps(english,ensure_ascii=False),encoding='utf8')
            (root/'catalog_english.json').write_text(json.dumps(english,ensure_ascii=False),encoding='utf8')
            (root/'catalog_overrides.json').write_text(json.dumps(overrides,ensure_ascii=False),encoding='utf8')
            editor=self.build_editor()
            try:
                self.assertEqual(editor._get_name(3574),'EP 1')
                self.assertEqual(editor._get_description(3574),'◆')
                self.assertEqual(editor._get_name(3807),'Купальник преподавателя — Юна')
                self.assertIn('Аурелии',editor._get_description(3807))
                editor.language_var.set('English');editor.change_language()
                self.assertEqual(editor._get_name(3574),'EP 1')
                self.assertEqual(editor._get_name(3807),'Faculty Swimsuit - Juna')
                editor.language_var.set('Русский');editor.change_language()
                self.assertEqual(editor._get_name(3574),'EP 1')
            finally: editor.destroy()

    def test_scanned_russian_neutral_name_not_tagged_as_en(self):
        with tempfile.TemporaryDirectory() as path, patch.dict(os.environ,{'APPDATA':path}):
            root=config_dir();root.mkdir(parents=True)
            records=[{'id':i,'name':f'Русский предмет {i}','description':'◆', 'category':'quest'} for i in range(100,130)]
            records.append({'id':3574,'name':'EP 1','description':'◆','category':'quartz_normal','kind':'quartz','element':'mirage'})
            (root/'catalog_scanned.json').write_text(json.dumps({'items':records},ensure_ascii=False),encoding='utf8')
            (root/'catalog_english.json').write_text(json.dumps({'items':[records[-1]]},ensure_ascii=False),encoding='utf8')
            editor=self.build_editor()
            try:
                self.assertEqual(editor._get_name(3574),'EP 1')
            finally: editor.destroy()
