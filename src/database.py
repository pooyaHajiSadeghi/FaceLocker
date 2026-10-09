"""Local JSON storage and cosine matching. Never stores photos."""
import json
import os
from pathlib import Path
import numpy as np

DEFAULTS = {'owner': 'pooya', 'camera_index': 0, 'threshold': 0.45,
            'margin': 0.05, 'samples': 10}

def unit(vector):
    vector = np.asarray(vector, dtype=np.float32).reshape(-1)
    norm = float(np.linalg.norm(vector))
    if vector.size != 128 or not np.isfinite(vector).all() or norm < 1e-8:
        raise ValueError('Invalid face feature: expected 128 finite values.')
    return vector / norm

def atomic_json(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    try:
        temporary.write_text(json.dumps(payload, ensure_ascii=False, allow_nan=False, indent=2), encoding='utf-8')
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)

def read_people(path):
    path = Path(path)
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(payload, dict) or payload.get('version') != 1 or not isinstance(payload.get('people'), dict):
        raise ValueError('Invalid people.json format.')
    people = {}
    for name, samples in payload['people'].items():
        if not isinstance(name, str) or not name.strip() or name.casefold() == 'unknown':
            raise ValueError('Invalid person name in people.json.')
        if not isinstance(samples, list) or not samples:
            raise ValueError(f'No valid samples for {name}.')
        people[name] = [unit(v).tolist() for v in samples]
    return people

def write_people(path, people):
    atomic_json(path, {'version': 1, 'people': people})

def read_config(path):
    config = DEFAULTS | (json.loads(Path(path).read_text(encoding='utf-8')) if Path(path).exists() else {})
    if not isinstance(config['owner'], str) or not config['owner'].strip():
        raise ValueError('Owner must be a name.')
    if type(config['camera_index']) is not int or config['camera_index'] < 0:
        raise ValueError('camera_index must be a nonnegative integer.')
    if not 0.1 <= config['threshold'] <= 0.95 or not 0 <= config['margin'] <= 0.5:
        raise ValueError('Invalid matching threshold or margin.')
    if type(config['samples']) is not int or not 3 <= config['samples'] <= 30:
        raise ValueError('samples must be between 3 and 30.')
    return config

def identify(vector, people, threshold=0.45, margin=0.05):
    vector = unit(vector)
    ranking = []
    for name, samples in people.items():
        scores = sorted(float(unit(v) @ vector) for v in samples)
        if scores:
            ranking.append((sum(scores[-3:]) / min(3, len(scores)), name))
    ranking.sort(reverse=True)
    if not ranking:
        return 'Unknown', 0.0
    score, name = ranking[0]
    ambiguous = len(ranking) > 1 and score - ranking[1][0] < margin
    return (name if score >= threshold and not ambiguous else 'Unknown'), score

def load_state(root):
    root=Path(root)
    path=root/'data'/'state.json'
    if path.exists():
        state=json.loads(path.read_text(encoding='utf-8'))
        if state.get('version')!=2:
            raise ValueError('Unsupported state.json version.')
        # Reuse strict validation for the stored enrollment format.
        for name,samples in state['people'].items():
            valid_name(name)
            if not isinstance(samples,list) or not samples:
                raise ValueError('Invalid enrollment samples.')
            for sample in samples: unit(sample)
        if not isinstance(state['folders'],list) or not all(isinstance(p,str) for p in state['folders']):
            raise ValueError('Invalid folder list.')
        # Old bilingual installations retain all data and use English on upgrade.
        state['language']='en'
        state.setdefault('theme','light')
        validate_settings(state)
        return state
    config=read_config(root/'config.json')
    people=read_people(root/'data'/'people.json')
    owner=config['owner']
    if people and owner not in people:
        raise ValueError('The existing owner is missing from people.json. Correct the old owner setting before migrating.')
    config['threshold']=max(0.45,config['threshold'])
    return {'version':2,'people':people,'folders':[], 'language':'en','theme':'light',**config}

def validate_settings(state):
    if state.get('theme','light') not in ('light','dark'):raise ValueError('Invalid theme.')
    valid_name(state['owner'])
    if state['people'] and state['owner'] not in state['people']:
        raise ValueError('The administrator enrollment is missing.')
    if type(state['camera_index']) is not int or not 0<=state['camera_index']<=20:
        raise ValueError('Invalid camera index.')
    if not 0.45<=state['threshold']<=0.95 or not 0<=state['margin']<=0.5:
        raise ValueError('Invalid matching settings.')
    if type(state['samples']) is not int or not 3<=state['samples']<=30:
        raise ValueError('Invalid enrollment count.')

def valid_name(name):
    if not isinstance(name,str) or not name.strip() or len(name)>60 or name.casefold()=='unknown':
        raise ValueError('Enter a name of 1–60 characters, other than Unknown.')
    return name.strip()

def save_state(root,state):
    validate_settings(state)
    atomic_json(Path(root)/'data'/'state.json',state)

def renamed_state(state,old,new):
    import copy
    new=valid_name(new)
    if old not in state['people']:
        raise ValueError('Person not found.')
    if new!=old and new in state['people']:
        raise ValueError('This name already exists.')
    result=copy.deepcopy(state)
    result['people'][new]=result['people'].pop(old)
    if result['owner']==old: result['owner']=new
    return result
