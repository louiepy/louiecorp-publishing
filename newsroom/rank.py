import re
from .config import KNOWLEDGE_FIELDS

UGANDA=['uganda','kampala','museveni','parliament of uganda','updf','electoral commission','bank of uganda','shilling','ugx']
AFRICA=['africa','kenya','tanzania','rwanda','congo','sudan','ethiopia','nigeria','south africa','ghana','somalia','burundi']
HIGH=['war','election','court','law','rights','government','president','parliament','economy','inflation','interest rate','conflict','death','disaster','outbreak','disease','climate','sanctions','trade','security','research','discovery','space']
LOW=['celebrity','fashion','gossip','viral','influencer','entertainment']

def candidate_text(c):
    return ' '.join([
        str(c.get('title') or ''),
        str(c.get('description') or ''),
        str(c.get('excerpt') or ''),
        str(c.get('feed') or ''),
        str(c.get('track') or ''),
    ]).lower()

def is_uganda(c):
    if str(c.get('track') or '').lower() == 'uganda':
        return True
    text = candidate_text(c)
    return any(k in text for k in UGANDA)

def score(c, track):
    text=(c['title']+' '+c.get('description','')).lower(); s=40
    if is_uganda(c) or any(k in text for k in UGANDA): s+=22
    elif any(k in text for k in AFRICA): s+=14
    if any(k in text for k in HIGH): s+=16
    if any(k in text for k in LOW): s-=24
    if track=='knowledge': s+=10
    if any(k in text for k in ['breaking','latest','today','announces','launches','approves']): s+=4
    return max(0,min(100,s))

def knowledge_topics(seed):
    idx=seed % len(KNOWLEDGE_FIELDS)
    return KNOWLEDGE_FIELDS[idx:]+KNOWLEDGE_FIELDS[:idx]
