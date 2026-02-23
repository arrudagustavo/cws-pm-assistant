import os
import re
import unicodedata
from atlassian import Jira
from crewai.tools import tool
from pinecone import Pinecone
from google import genai
from dotenv import load_dotenv

load_dotenv()

# ==========================================
# 1. MOTOR TÉCNICO (BUSCA VETORIAL 768)
# ==========================================

def get_query_embedding(text):
    try:
        client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
        result = client.models.embed_content(model="models/gemini-embedding-001", contents=text.replace('\x00', '').strip())
        return result.embeddings[0].values[:768] 
    except: return [0.0] * 768

@tool("Consultar Base de Conhecimento CWS")
def consultar_base_cws(query: str) -> str:
    """Busca detalhes técnicos nos manuais da CWS."""
    try:
        pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
        index = pc.Index(os.getenv("PINECONE_INDEX_NAME"))
        vector = get_query_embedding(query)
        res = index.query(vector=vector, top_k=10, include_metadata=True)
        if not res['matches'] or res['matches'][0]['score'] < 0.35:
            return "RESULTADO: Nada encontrado na base técnica."
        return "\n\n---\n\n".join([f"[{m['metadata'].get('source')}]: {m['metadata']['text']}" for m in res['matches']])
    except Exception as e: return f"Erro: {str(e)}"

# ==========================================
# 2. LÓGICA JIRA (COM COMENTÁRIO DE IA E FIX DE TEXTO)
# ==========================================

def _get_jira_client():
    url, user, token = os.getenv("JIRA_SERVER_URL"), os.getenv("JIRA_EMAIL"), os.getenv("JIRA_API_TOKEN")
    if not all([url, user, token]): return None
    return Jira(url=url, username=user, password=token, cloud=True)

def get_jira_projects():
    j = _get_jira_client()
    try:
        projs = j.get("rest/api/2/project")
        return {p['key']: p['name'] for p in projs}
    except: return {"CWS": "CWS Default"}

def get_jira_priorities():
    j = _get_jira_client()
    try:
        pris = j.get("rest/api/2/priority")
        return [p['name'] for p in pris]
    except: return ["High", "Medium", "Low"]

def get_project_custom_fields_meta(project_key):
    j = _get_jira_client()
    meta = {"client": {"id": None, "options": []}, "param": {"id": None, "allowed_values": []}}
    try:
        res = j.get(f"rest/api/2/issue/createmeta?projectKeys={project_key}&expand=projects.issuetypes.fields")
        fields = res['projects'][0]['issuetypes'][0]['fields']
        for fk, fi in fields.items():
            n = fi['name'].lower()
            if "cliente" in n: meta["client"] = {"id": fk, "options": [o['value'] for o in fi.get('allowedValues', [])], "is_array": (fi['schema']['type'] == 'array')}
            if "parametri" in n: meta["param"] = {"id": fk, "allowed_values": [o['value'] for o in fi.get('allowedValues', [])], "is_array": (fi['schema']['type'] == 'array')}
        return meta
    except: return meta

def create_jira_issue_manual(project_key, summary, description, priority, client_value=None, param_value=None, custom_field_meta=None):
    j = _get_jira_client()
    try:
        pj = j.get(f"rest/api/2/project/{project_key}")
        sid = next((t['id'] for t in pj['issueTypes'] if t['name'].lower() in ["story", "história"]), "10001")
        
        # --- FIX DE FORMATAÇÃO ---
        clean_desc = description.replace('\r\n', '\n')
        formatted_desc = re.sub(r'\n+', '\n\n', clean_desc).strip()

        issue_dict = {
            'project': {'key': project_key}, 
            'summary': summary, 
            'description': formatted_desc, 
            'issuetype': {'id': sid}, 
            'priority': {'name': priority}
        }
        
        if custom_field_meta:
            for k, val in [('client', client_value), ('param', param_value)]:
                m = custom_field_meta.get(k, {})
                if m.get('id') and val:
                    v = {'value': val}
                    issue_dict[m['id']] = [v] if m.get('is_array') else v
        
        # 1. Cria o Ticket
        res = j.issue_create(fields=issue_dict)
        ticket_key = res['key']

        # 2. ADICIONA COMENTÁRIO DE IA (FUNCIONALIDADE RESTAURADA)
        try:
            comment_text = "✨ História criada e adicionada ao JIRA via CWS PM Assistant (AI Powered)."
            j.issue_add_comment(ticket_key, comment_text)
        except Exception as e_comm:
            print(f"Erro ao adicionar comentário: {e_comm}")

        return ticket_key, f"{os.getenv('JIRA_SERVER_URL').rstrip('/')}/browse/{ticket_key}"
    except Exception as e: return None, str(e)