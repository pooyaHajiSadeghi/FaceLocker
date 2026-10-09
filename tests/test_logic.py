import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
import numpy as np
from database import unit, identify, read_people, write_people, read_config, atomic_json
from locker import Gate, Locker, attributes_with_hidden, VerifiedAction, apply_batch, prepare_jobs
from database import load_state, save_state, renamed_state

class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.a=np.eye(128,dtype=np.float32)[0]
        self.b=np.eye(128,dtype=np.float32)[1]

    def test_known_unknown_and_empty(self):
        people={'pooya':[self.a.tolist()]*3}
        self.assertEqual(identify(self.a,people)[0],'pooya')
        self.assertEqual(identify(self.b,people)[0],'Unknown')
        self.assertEqual(identify(self.a,{})[0],'Unknown')

    def test_ambiguous_does_not_match(self):
        people={'pooya':[self.a.tolist()],'other':[self.a.tolist()]}
        self.assertEqual(identify(self.a,people)[0],'Unknown')

    def test_invalid_features(self):
        for vector in ([1,2],np.zeros(128),np.full(128,np.nan)):
            with self.assertRaises(ValueError): unit(vector)

    def test_persistence_import_compatibility_and_deletion(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'data'/'people.json'
            write_people(path,{'pooya':[self.a.tolist()],'رزا':[self.b.tolist()]})
            self.assertEqual(set(read_people(path)),{'pooya','رزا'})
            self.assertEqual(identify(self.a,read_people(path))[0],'pooya')
            write_people(path,{})
            self.assertEqual(read_people(path),{})
            path.write_text('{broken')
            with self.assertRaises(ValueError): read_people(path)

    def test_atomic_failure_preserves_original(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'config.json';atomic_json(path,{'old':1})
            with patch('database.os.replace',side_effect=OSError('disk error')):
                with self.assertRaises(OSError): atomic_json(path,{'new':2})
            self.assertIn('old',path.read_text())
            self.assertFalse(path.with_suffix('.tmp').exists())

    def test_config_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'config.json'
            self.assertEqual(read_config(path)['owner'],'pooya')
            atomic_json(path,{'camera_index':-1})
            with self.assertRaises(ValueError): read_config(path)

class GateTests(unittest.TestCase):
    def test_matches_need_time_and_count(self):
        gate=Gate(0)
        for i in range(8): self.assertFalse(gate.update(True,i*0.1))
        self.assertTrue(gate.update(True,1.3))

    def test_failure_resets_streak_and_timeout_rejects(self):
        gate=Gate(0)
        for i in range(7): gate.update(True,i*0.2)
        self.assertFalse(gate.update(False,1.5))
        self.assertEqual(gate.count,0)
        self.assertFalse(gate.update(True,1.7))
        self.assertFalse(gate.update(True,30))
        self.assertTrue(gate.expired(30))

class FolderTests(unittest.TestCase):
    def test_attribute_flags_preserved(self):
        for attributes in (16,17,48,18,0x2010):
            hidden=attributes_with_hidden(attributes,True)
            self.assertTrue(hidden&2)
            self.assertEqual(hidden&~2,attributes&~2)
            self.assertEqual(attributes_with_hidden(hidden,False)&~2,attributes&~2)
        self.assertEqual(attributes_with_hidden(128,True),2)
        self.assertEqual(attributes_with_hidden(2,False),128)

    def test_open_failure_rehides(self):
        locker=Locker.__new__(Locker);locker.path=Path('Locker')
        locker.visibility=Mock();locker.hide=Mock()
        with patch('locker.os.startfile',create=True,side_effect=OSError('Explorer unavailable')):
            with self.assertRaises(OSError): locker.open()
        locker.visibility.assert_called_once_with(False)
        locker.hide.assert_called_once()

    def test_cancel_discards_verified_action(self):
        from app import App
        app=App.__new__(App)
        action=VerifiedAction('pooya',0,[('folder',True)])
        app.pending=action;app.mode='verify';app.pipeline=Mock();app.popup=None
        app.blank=Mock();app.canvas=Mock();app.notify=Mock()
        app.stop('cancelled')
        self.assertFalse(action.active)
        self.assertEqual(app.mode,'idle')
        app.pipeline.stop.assert_called_once()

class VerificationControllerTests(unittest.TestCase):
    def exercise(self, identities, hidden=True, purpose='folders'):
        from app import App
        app=App.__new__(App)
        a=np.eye(128,dtype=np.float32)[0]
        b=np.eye(128,dtype=np.float32)[1]
        app.state={'people':{'pooya':[a.tolist()],'other':[b.tolist()]},'owner':'pooya','threshold':0.45,'margin':0.05}
        app.mode='verify';app.closed=False
        app.pending=VerifiedAction('pooya',90,[('selected',hidden)],purpose)
        app.pending.gate.count=7;app.pending.gate.first=90
        app.pipeline=Mock()
        faces=[((50,50,100,100),a if name=='pooya' else b) for name in identities]
        app.pipeline.read.return_value=(np.zeros((480,640,3),np.uint8),faces)
        app.render=Mock();app.notify=Mock();app.root=Mock()
        app.stop=Mock();app.refresh_folders=Mock();app.refresh_admin=Mock();app.notebook=Mock();app.admin_unlocked=False
        with patch('app.time.monotonic',return_value=100),patch('app.prepare_jobs',side_effect=lambda jobs,root:jobs),patch('app.apply_batch',return_value=[('selected',True,'')]) as batch:
            app.tick()
        return app,batch

    def test_only_owner_can_unlock(self):
        self.exercise(['pooya'])[1].assert_called_once()
        self.exercise(['other'])[1].assert_not_called()

    def test_two_faces_or_no_face_never_unlock(self):
        self.exercise(['pooya','other'])[1].assert_not_called()
        self.exercise([])[1].assert_not_called()

    def test_hide_and_unhide_use_verified_snapshot(self):
        for hidden in (True,False):
            self.exercise(['pooya'],hidden)[1].assert_called_once_with((('selected',hidden),))

    def test_admin_entry_does_not_change_folders(self):
        app,batch=self.exercise(['pooya'],purpose='admin')
        self.assertTrue(app.admin_unlocked);batch.assert_not_called()
        app,batch=self.exercise(['other'],purpose='admin')
        self.assertFalse(app.admin_unlocked);batch.assert_not_called()

class V2Tests(unittest.TestCase):
    def test_atomic_owner_rename_and_legacy_migration(self):
        a=np.eye(128,dtype=np.float32)[0]
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);write_people(root/'data'/'people.json',{'pooya':[a.tolist()]})
            before=(root/'data'/'people.json').read_bytes()
            state=load_state(root);new=renamed_state(state,'pooya','پویا')
            self.assertEqual(new['owner'],'پویا');self.assertIn('pooya',state['people'])
            save_state(root,new);self.assertEqual(load_state(root)['owner'],'پویا')
            self.assertEqual((root/'data'/'people.json').read_bytes(),before)

    def test_rename_collision_rejected(self):
        state={'people':{'a':[[1]],'b':[[1]]},'owner':'a'}
        with self.assertRaises(ValueError):renamed_state(state,'a','b')

    def test_one_shot_and_cancelled_verification(self):
        action=VerifiedAction('pooya',0,[('A',True),('B',False)])
        for i in range(7):self.assertFalse(action.consume('pooya',1,i*.2))
        self.assertTrue(action.consume('pooya',1,1.5))
        self.assertFalse(action.consume('pooya',1,2))
        action=VerifiedAction('pooya',0);action.cancel()
        for i in range(10):self.assertFalse(action.consume('pooya',1,i*.2))

    def test_jobs_snapshot_is_independent(self):
        jobs=[('A',True),('B',False)];action=VerifiedAction('pooya',0,jobs);jobs.clear()
        self.assertEqual(action.jobs,(('A',True),('B',False)))

    def test_mixed_batch_partial_failure(self):
        applied=[]
        class Fake:
            def __init__(self,path):self.path=path
            def visibility(self,hidden):
                if self.path=='bad':raise OSError('denied')
                applied.append((self.path,hidden))
        result=apply_batch([('A',True),('B',False),('bad',True)],Fake)
        self.assertEqual(applied,[('A',True),('B',False)])
        self.assertEqual([ok for _,ok,_ in result],[True,True,False])

    def test_preflight_failure_does_not_change_anything(self):
        applied=[]
        class Fake:
            def __init__(self,path):
                if path=='missing':raise ValueError('missing')
                self.path=path
            def visibility(self,hidden):applied.append(hidden)
        with self.assertRaises(ValueError):apply_batch([('A',True),('missing',False)],Fake)
        self.assertEqual(applied,[])

    def test_parent_child_conflict_and_missing_path(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);project=root/'app';project.mkdir();a=root/'A';a.mkdir();b=a/'child';b.mkdir()
            self.assertEqual(len(prepare_jobs([(str(a),True)],project)),1)
            with self.assertRaises(ValueError):prepare_jobs([(str(a),True),(str(b),False)],project)
            with self.assertRaises(ValueError):prepare_jobs([(str(project),True)],project)
            with self.assertRaises(ValueError):prepare_jobs([(str(root/'missing'),False)],project)

    def test_english_messages(self):
        from strings import STRINGS,text
        self.assertTrue(all(isinstance(value,str) for value in STRINGS.values()))
        self.assertEqual(text('owner_saved',name='pooya'),'Administrator: pooya')
        self.assertFalse(any(any('\u0600'<=ch<='\u06ff' for ch in value) for value in STRINGS.values()))

if __name__=='__main__':
    unittest.main()
