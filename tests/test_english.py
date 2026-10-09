import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import json
import tempfile
import unittest
from pathlib import Path
from database import load_state,save_state
from strings import text

class EnglishUpgradeTests(unittest.TestCase):
    def test_old_persian_state_keeps_enrollment_and_folders(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            state=load_state(root)
            vector=[1.0]+[0.0]*127
            state.update(language='fa',owner='pooya',people={'pooya':[vector]},folders=['D:\\Documents'],theme='dark')
            save_state(root,state)
            loaded=load_state(root)
            self.assertEqual(loaded['language'],'en')
            for key in ('people','owner','folders','theme'):
                self.assertEqual(loaded[key],state[key])
            self.assertEqual(text('verifying',owner=loaded['owner'],count=3,seconds=29),'Verify pooya | matches 3/8 | 29s')

    def test_new_installation_uses_english(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(load_state(directory)['language'],'en')

if __name__=='__main__':unittest.main()
