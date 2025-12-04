import os
from atlassian import Jira
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

# --- CONEXÃO JIRA ---
def _get_jira_client():
    jira_url = os.environ.get("JIRA_SERVER_URL")
    jira_user = os.environ.get("JIRA_EMAIL")
    jira_token = os.environ.get("JIRA_API_TOKEN")

    if not all([jira_url, jira_user, jira_token]):
        return None
    return Jira(url=jira_url, username=jira_user, password=jira_token, cloud=True)

# --- LEITURAS BÁSICAS ---
def get_jira_projects():
    jira = _get_jira_client()
    if not jira: return {}
    try:
        projects = jira.get("rest/api/2/project")
        return {p['key']: p['name'] for p in projects}
    except Exception as e:
        print(f"Erro Projects: {e}")
        return {"CWS": "CWS Default"}

def get_jira_priorities():
    jira = _get_jira_client()
    if not jira: return []
    try:
        priorities = jira.get("rest/api/2/priority")
        return [p['name'] for p in priorities]
    except Exception as e:
        print(f"Erro Priorities: {e}")
        return ["Medium", "High"]

# --- INTEGRAÇÃO AVANÇADA: METADADOS DE CAMPOS ---
def get_project_custom_fields_meta(project_key):
    """
    Busca IDs, Opções e TIPO (Schema) dos campos personalizados.
    Detecta se o campo exige uma matriz (array) ou valor único.
    """
    jira = _get_jira_client()
    if not jira: return {}

    meta_data = {
        "client": {"id": None, "options": [], "is_array": False},
        "param": {"id": None, "allowed_values": [], "is_array": False}
    }

    try:
        query = f"rest/api/2/issue/createmeta?projectKeys={project_key}&expand=projects.issuetypes.fields"
        response = jira.get(query)

        if 'projects' not in response or len(response['projects']) == 0:
            return meta_data

        issue_types = response['projects'][0]['issuetypes']
        
        # Tenta achar o tipo História
        story_type = next((it for it in issue_types if it['name'] in ['História', 'Story', 'User Story']), issue_types[0])
        fields = story_type.get('fields', {})

        for field_key, field_info in fields.items():
            name = field_info['name'].lower()
            schema_type = field_info.get('schema', {}).get('type', '')
            
            # --- CLIENTE/SPONSOR ---
            if "cliente" in name or "sponsor" in name:
                meta_data["client"]["id"] = field_key 
                meta_data["client"]["is_array"] = (schema_type == 'array')
                if 'allowedValues' in field_info:
                    meta_data["client"]["options"] = [opt['value'] for opt in field_info['allowedValues']]
            
            # --- PARAMETRIZAÇÃO ---
            if "parametrização" in name or "parametrizacao" in name:
                meta_data["param"]["id"] = field_key
                meta_data["param"]["is_array"] = (schema_type == 'array')
                if 'allowedValues' in field_info:
                     meta_data["param"]["allowed_values"] = [opt['value'] for opt in field_info['allowedValues']]

        return meta_data

    except Exception as e:
        print(f"Erro ao buscar metadados: {e}")
        return meta_data

def _get_project_specific_story_id(jira, project_key):
    try:
        project_data = jira.get(f"rest/api/2/project/{project_key}")
        if 'issueTypes' not in project_data: return "10001" 
        issue_types = project_data['issueTypes']
        target_names = ["História", "Story", "User Story", "Historia"]
        for name in target_names:
            for t in issue_types:
                if t['name'].lower() == name.lower(): return t['id']
        for t in issue_types:
            if not t.get('subtask', False) and "bug" not in t['name'].lower(): return t['id']
        return "10001"
    except: return "10001"

# --- CRIAÇÃO DE TICKET + COMENTÁRIO ---
def create_jira_issue_manual(project_key, summary, description, priority, client_value=None, param_value=None, custom_field_meta=None):
    jira = _get_jira_client()
    if not jira: return None, "⚠️ Credenciais inválidas."

    try:
        # 1. Busca ID da História
        story_id = _get_project_specific_story_id(jira, project_key)

        issue_dict = {
            'project': {'key': project_key},
            'summary': summary,
            'description': description, 
            'issuetype': {'id': story_id},
            'priority': {'name': priority},
        }

        # 2. Injeção Dinâmica
        if custom_field_meta:
            # Campo Cliente
            c_meta = custom_field_meta.get('client', {})
            c_id = c_meta.get('id')
            if c_id and client_value:
                payload_value = {'value': client_value}
                if c_meta.get('is_array', False):
                    issue_dict[c_id] = [payload_value]
                else:
                    issue_dict[c_id] = payload_value
            
            # Campo Parametrização
            p_meta = custom_field_meta.get('param', {})
            p_id = p_meta.get('id')
            if p_id and param_value:
                payload_value = {'value': param_value}
                if p_meta.get('is_array', False):
                    issue_dict[p_id] = [payload_value]
                else:
                    issue_dict[p_id] = payload_value

        # 3. Cria o Ticket
        new_issue = jira.issue_create(fields=issue_dict)
        ticket_key = new_issue['key']

        # --- 4. NOVO: ADICIONA O COMENTÁRIO AUTOMÁTICO ---
        try:
            jira.issue_add_comment(ticket_key, "História criada e adicionada ao JIRA via CWS PM Assistant.")
            print(f"Comentário adicionado em {ticket_key}")
        except Exception as e_comm:
            # Não falha o processo se só o comentário der erro, apenas loga
            print(f"⚠️ Aviso: Ticket criado, mas erro ao comentar: {e_comm}")

        # 5. Retorno
        base_url = os.environ.get('JIRA_SERVER_URL', '').rstrip('/')
        ticket_link = f"{base_url}/browse/{ticket_key}"
        
        return ticket_key, ticket_link

    except Exception as e:
        return None, f"❌ Erro do Jira: {str(e)}"

# --- TOOL ---
class JiraToolInput(BaseModel):
    summary: str = Field(..., description="Título")
    description: str = Field(..., description="Conteúdo")
    project_key: str = Field(..., description="Chave do Projeto")

class CreateJiraTicketTool(BaseTool):
    name: str = "Create Jira Ticket"
    description: str = "Cria uma Story no Jira."
    args_schema: type[BaseModel] = JiraToolInput

    def _run(self, summary: str, description: str, project_key: str) -> str:
        key, link = create_jira_issue_manual(project_key, summary, description, "Medium")
        return f"Ticket criado: {key}" if key else link