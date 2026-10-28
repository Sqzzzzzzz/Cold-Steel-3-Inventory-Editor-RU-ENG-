"""Isolation of beta profile from stable user config; no user saves are copied."""
from __future__ import annotations
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from beta_config import seed_beta_profile,user_root,beta_dir,BETA_FOLDER,STABLE_FOLDER
from catalog_core import user_catalog_path
from game_scan import config_dir,load_settings,save_settings
from game_icons import icon_cache_dir

class ProfileTests(unittest.TestCase):
    def test_migration_copies_known_files_but_never_writes_stable(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ,{'APPDATA':tmp}):
            stable=Path(tmp)/STABLE_FOLDER
            stable.mkdir()
            stable_settings=stable/'settings.json'
            stable_settings.write_text('{"theme":"dark","language":"ru","auto_latest":false}',encoding='utf-8')
            (stable/'catalog_overrides.json').write_text('old-private-text',encoding='utf-8')
            source=stable/'icons'/'original'
            source.mkdir(parents=True)
            (source/'fake.png').write_bytes(b'synthetic-image')
            expected_settings=stable_settings.read_bytes()
            beta=seed_beta_profile()
            self.assertEqual(beta,Path(tmp)/BETA_FOLDER)
            self.assertEqual(config_dir(),beta)
            self.assertEqual(user_catalog_path(),beta/'catalog_overrides.json')
            self.assertEqual(icon_cache_dir(),beta/'icons'/'original')
            self.assertEqual((beta/'catalog_overrides.json').read_text(),'old-private-text')
            self.assertEqual((beta/'icons'/'original'/'fake.png').read_bytes(),b'synthetic-image')
            self.assertEqual(load_settings()['theme'],'game')
            options=load_settings();options['language']='en'
            save_settings(options)
            self.assertEqual(stable_settings.read_bytes(),expected_settings)

    def test_seeding_is_one_time_never_overwrites_beta_edits(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ,{'APPDATA':tmp}):
            stable=Path(tmp)/STABLE_FOLDER
            stable.mkdir()
            (stable/'settings.json').write_text('STABLE1',encoding='utf-8')
            beta=seed_beta_profile()
            (beta/'settings.json').write_text('BETA EDIT',encoding='utf-8')
            (stable/'settings.json').write_text('STABLE2',encoding='utf-8')
            seed_beta_profile()
            self.assertEqual((beta/'settings.json').read_text(),'BETA EDIT')
            self.assertEqual((stable/'settings.json').read_text(),'STABLE2')

    def test_no_backups_or_saves_are_copied(self):
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'APPDATA':tmp}):
            stable=Path(tmp)/STABLE_FOLDER
            stable.mkdir()
            (stable/'save016.dat').write_bytes(b'mock game save')
            (stable/'secret.bin').write_bytes(b'private data')
            beta=seed_beta_profile()
            self.assertFalse((beta/'save016.dat').exists())
            self.assertFalse((beta/'secret.bin').exists())

if __name__=='__main__':unittest.main()
