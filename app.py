import os
import sys
import time 

# --- 1. CONFIGURAÇÕES DE AMBIENTE (ANTI-TRAVAMENTO) ---
os.environ["CREWAI_TELEMETRY_OPT_OUT"] = "true"
os.environ["OTEL_SDK_DISABLED"] = "true"

import streamlit as st
from crewai import Crew, Process
from agents import CWSCrewAgents
from tasks import CWSCrewTasks
# Importamos as ferramentas blindadas
from tools import create_jira_issue_manual, get_jira_projects, get_jira_priorities, get_project_custom_fields_meta
from file_handler import extract_text_from_file, generate_docx, generate_pdf
from dotenv import load_dotenv

load_dotenv()

# --- CSS CUSTOMIZADO ---
def local_css():
    st.markdown("""
    <style>
        .stTextArea textarea {font-size: 16px !important;}
        .stButton button {width: 100%; border-radius: 8px; height: 50px; font-weight: bold;}
        div[data-testid="stExpander"] div[role="button"] p {font-size: 1.1rem; font-weight: 600;}
        h1 {color: #2E4053;}
        h2 {color: #2874A6; font-size: 1.8rem; margin-top: 20px;}
        h3 {color: #17A589;}
        .stSpinner > div {border-top-color: #2874A6 !important;}
        
        /* Destaque visual para campos obrigatórios */
        label:after {
            content: " *";
            color: red;
            visibility: hidden; 
        }
    </style>
    """, unsafe_allow_html=True)

def extract_title_from_story(story_text):
    """Extrai a primeira linha do texto gerado para usar como título sugerido"""
    if not story_text: return ""
    first_line = story_text.strip().split('\n')[0]
    clean_title = first_line.replace('#', '').replace('*', '').strip()
    return clean_title[:254] # Limite do Jira

def main():
    # Configuração da Página
    st.set_page_config(page_title="CWS PM Assistant", page_icon="🚀", layout="wide")
    local_css() 

    # --- CONFIG ---
    MODEL_NAME = "gemini-2.5-flash"
    API_KEY = os.getenv("GOOGLE_API_KEY")
    JIRA_PROJECT_KEY = os.getenv("JIRA_PROJECT_KEY", "CWS")

    # --- CARREGAMENTO DE DADOS JIRA (CACHEADO) ---
    @st.cache_data(ttl=3600)
    def load_jira_data():
        if os.getenv("JIRA_SERVER_URL"):
            return get_jira_projects(), get_jira_priorities()
        return {}, []

    available_projects, available_priorities = load_jira_data()
    
    # Fallbacks de segurança
    if not available_projects: available_projects = {"CWS": "CWS Default"}
    if not available_priorities: available_priorities = ["Medium"]

    # --- SIDEBAR ---
    with st.sidebar:
        st.image("https://placehold.co/200x80/2874A6/FFFFFF/png?text=CWS+Digital", width=200) 
        st.markdown("### ⚙️ Status do Sistema")
        
        if API_KEY:
            st.success("Google Gemini: Conectado 🟢")
        else:
            st.error("Google Gemini: Desconectado 🔴")
            
        st.info(f"Jira Spaces: **{len(available_projects)}**")
        st.caption("v3.2.1 - Clean UI")

    if not API_KEY:
        st.warning("⚠️ Sistema Pausado: Configure a API Key no arquivo .env ou Secrets.")
        st.stop()

    # --- CABEÇALHO ---
    st.markdown("# 🚀 CWS PM Assistant")
    st.markdown("##### Seu copiloto de Produto para transformar inputs de Discovery em Histórias de Usuário técnicas, validadas e integradas ao Jira.")
    st.divider()

    # --- 1. ÁREA DE INPUT ---
    st.markdown("### 1. 📥 Ingestão de Contexto")
    
    input_container = st.container(border=True)
    final_input_text = ""

    with input_container:
        tab1, tab2 = st.tabs(["📝 Digitar Contexto", "📂 Upload de Arquivo"])
        
        # ABA 1: Texto
        with tab1:
            manual_text = st.text_area(
                "Descreva a necessidade de negócio:", 
                height=200, 
                placeholder="Ex: Como vendedor, quero poder aprovar o frete...",
                key="input_manual"
            )
        
        # ABA 2: Arquivo
        with tab2:
            uploaded_file = st.file_uploader(
                "Arraste documentos (PDF, DOCX, PPTX, Excel, TXT)", 
                type=["docx", "pdf", "txt", "md", "pptx", "xlsx", "xls"],
                key="input_file"
            )
            
            # Lógica de processamento imediato do arquivo
            if uploaded_file:
                with st.spinner("Lendo arquivo..."):
                    extracted_text = extract_text_from_file(uploaded_file)
                
                # Feedback simples, sem mostrar o texto
                st.success(f"✅ Arquivo **{uploaded_file.name}** carregado com sucesso!")
                
                final_input_text = f"ARQUIVO ({uploaded_file.name}):\n{extracted_text}"
                
                # Se tiver texto manual também, concatena
                if manual_text:
                    final_input_text += f"\n\nOBSERVAÇÕES MANUAIS:\n{manual_text}"
            else:
                final_input_text = manual_text

    # Feedback visual fora das abas para confirmar a fonte
    if uploaded_file:
        st.info(f"📎 **Fonte de Dados:** Utilizando arquivo '{uploaded_file.name}' como base principal.")
    elif manual_text:
        st.info("✍️ **Fonte de Dados:** Utilizando texto digitado manualmente.")

    st.markdown("<br>", unsafe_allow_html=True)

    # --- 2. BOTÃO DE AÇÃO ---
    col_spacer1, col_btn, col_spacer2 = st.columns([1, 2, 1])
    
    with col_btn:
        run_process = st.button("✨ GERAR HISTÓRIA DE USUÁRIO", type="primary", use_container_width=True)

    # --- LÓGICA DE EXECUÇÃO ---
    if run_process:
        if not final_input_text or len(final_input_text) < 5:
            st.toast("⚠️ Por favor, forneça um input válido.", icon="⚠️")
        else:
            progress_placeholder = st.empty()
            with progress_placeholder.container():
                st.info("🤖 **Squad CWS Iniciado:** Os agentes estão trabalhando nos requisitos...")
                
                with st.spinner("Analisando contexto, consultando documentação e escrevendo Gherkin... Por favor, aguarde."):
                    try:
                        # Instancia Agentes
                        agents = CWSCrewAgents(google_api_key=API_KEY, model_name=MODEL_NAME)
                        analyst = agents.context_interpreter_agent()
                        architect = agents.story_architect_agent()
                        gatekeeper = agents.gatekeeper_agent()

                        # Define Tarefas
                        tasks = CWSCrewTasks()
                        t1 = tasks.analysis_task(analyst, final_input_text)
                        t2 = tasks.drafting_task(architect, [t1])
                        t3 = tasks.publication_task(gatekeeper, [t2], "CWS-Plataform")

                        # Executa Crew
                        crew = Crew(
                            agents=[analyst, architect, gatekeeper],
                            tasks=[t1, t2, t3],
                            process=Process.sequential,
                            verbose=True 
                        )

                        result = crew.kickoff()
                        
                        # Salva Resultado na Sessão
                        st.session_state['final_story'] = result.raw
                        st.session_state['task_outputs'] = [t1.output.raw, t2.output.raw]
                        st.session_state['auto_title'] = extract_title_from_story(result.raw)
                    
                    except Exception as e:
                        st.error(f"Erro na execução: {str(e)}")
            
            progress_placeholder.empty()
            st.success("✅ Processo Finalizado com Sucesso!")


    # --- 3. ÁREA DE RESULTADO ---
    if 'final_story' in st.session_state:
        st.divider()
        st.markdown("### 2. 💎 Refinamento e Entrega")

        st.markdown("#### 🖊️ Editor da História")
        final_content_edited = st.text_area(
            label="Conteúdo Final (Markdown)",
            value=st.session_state['final_story'],
            height=600,
            label_visibility="collapsed"
        )
        
        st.markdown("<br>", unsafe_allow_html=True)

        st.markdown("#### 🧠 Inteligência dos Agentes")
        col_intel1, col_intel2 = st.columns(2)
        with col_intel1:
            with st.expander("🔍 Ver Análise Técnica (Analista)"):
                st.markdown(st.session_state['task_outputs'][0])
        with col_intel2:
            with st.expander("📝 Ver Rascunho Inicial (Arquiteto)"):
                st.markdown(st.session_state['task_outputs'][1])

        st.markdown("<br>", unsafe_allow_html=True)

        st.markdown("#### 💾 Exportar Documento")
        dl_container = st.container(border=True)
        with dl_container:
            col_d1, col_d2, col_d3, col_d4 = st.columns(4)
            with col_d1:
                st.download_button("📄 Baixar DOCX", data=generate_docx(final_content_edited), file_name="historia.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document", use_container_width=True)
            with col_d2:
                st.download_button("📕 Baixar PDF", data=generate_pdf(final_content_edited), file_name="historia.pdf", mime="application/pdf", use_container_width=True)
            with col_d3:
                st.download_button("📝 Baixar TXT", data=final_content_edited, file_name="historia.txt", mime="text/plain", use_container_width=True)
            with col_d4:
                st.download_button("👾 Baixar Markdown", data=final_content_edited, file_name="historia.md", mime="text/markdown", use_container_width=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # --- 4. JIRA CONTAINER (COM VALIDAÇÃO) ---
        jira_container = st.container(border=True)
        with jira_container:
            st.markdown("### 🚀 Publicar no Jira")
            st.caption("Todos os campos marcados com * são obrigatórios.")
            
            # LINHA 1: Título e Squad
            j_col1, j_col2 = st.columns([3, 2])
            
            with j_col1:
                default_title = st.session_state.get('auto_title', "")
                ticket_title = st.text_input("1. Resumo (Título da Demanda) *", value=default_title, placeholder="Digite o título...")
            
            with j_col2:
                # SQUAD (Vazio por padrão)
                project_options = list(available_projects.keys())
                def format_func(key):
                    return f"{key} - {available_projects[key]}"
                
                selected_project_key = st.selectbox(
                    "2. Espaço (Squad) *", 
                    options=project_options, 
                    format_func=format_func,
                    index=None, # Força o usuário a escolher
                    placeholder="Selecione a Squad..."
                )
            
            # --- BUSCA DINÂMICA DE METADADOS ---
            # Só busca se uma Squad foi selecionada
            meta_fields = {}
            client_options = []
            param_options = ["Sim", "Não"]
            client_id = None
            param_id = None
            
            if selected_project_key:
                with st.spinner(f"Carregando campos da Squad {selected_project_key}..."):
                    meta_fields = get_project_custom_fields_meta(selected_project_key)
                    # Popula opções vindas do Jira
                    client_options = meta_fields.get("client", {}).get("options", [])
                    client_id = meta_fields.get("client", {}).get("id")
                    param_options = meta_fields.get("param", {}).get("allowed_values", ["Sim", "Não"])
                    param_id = meta_fields.get("param", {}).get("id")
            
            # LINHA 2: Prioridade, Cliente e Parametrização
            j_col3, j_col4, j_col5 = st.columns([1, 1, 1])
            
            with j_col3:
                # Prioridade (Vazio por padrão)
                priority = st.selectbox(
                    "3. Prioridade *", 
                    available_priorities, 
                    index=None,
                    placeholder="Selecione..."
                )

            with j_col4:
                # CLIENTE (Vazio por padrão)
                client_placeholder = "Selecione a Squad antes" if not selected_project_key else "Selecione..."
                client_sponsor = st.selectbox(
                    "4. Cliente / Sponsor *", 
                    options=client_options,
                    index=None, 
                    placeholder=client_placeholder,
                    disabled=(not selected_project_key) # Trava se não tiver Squad
                )
            
            with j_col5:
                # PARAMETRIZAÇÃO
                needs_param_str = st.radio("5. Parametrização? *", param_options, horizontal=True)

            st.markdown("<br>", unsafe_allow_html=True)
            
            # --- BOTÃO COM VALIDAÇÃO ---
            if st.button("Confirmar e Criar Ticket Jira ➔", type="primary", use_container_width=True):
                
                # Validação de Obrigatórios
                missing_fields = []
                if not ticket_title: missing_fields.append("Resumo")
                if not selected_project_key: missing_fields.append("Espaço (Squad)")
                if not priority: missing_fields.append("Prioridade")
                if not client_sponsor: missing_fields.append("Cliente/Sponsor")
                
                if missing_fields:
                    st.error(f"❌ Campos obrigatórios faltando: {', '.join(missing_fields)}")
                else:
                    # Envio
                    ticket_id, ticket_link = create_jira_issue_manual(
                        project_key=selected_project_key, 
                        summary=ticket_title, 
                        description=final_content_edited, 
                        priority=priority,
                        client_value=client_sponsor,
                        param_value=needs_param_str,
                        custom_field_meta=meta_fields
                    )
                    
                    if ticket_id:
                        st.balloons()
                        st.markdown(f"""
                        <div style="background-color: #D4EFDF; padding: 20px; border-radius: 10px; text-align: center; border: 1px solid #28B463;">
                            <h2 style="color: #196F3D; margin:0;">✅ Ticket Criado!</h2>
                            <h1 style="font-size: 50px; margin: 10px 0;">{ticket_id}</h1>
                            <a href="{ticket_link}" target="_blank" style="font-size: 18px; color: #196F3D; font-weight: bold; text-decoration: none;">🔗 Clique para abrir no Jira</a>
                        </div>
                        """, unsafe_allow_html=True)
                    else:
                        st.error(ticket_link)

if __name__ == "__main__":
    main()