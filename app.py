import os
import sys
import base64 
import unicodedata
import re
import time
import streamlit as st
from crewai import Crew, Process
from agents import CWSCrewAgents
from tasks import CWSCrewTasks
from tools import create_jira_issue_manual, get_jira_projects, get_jira_priorities, get_project_custom_fields_meta
from file_handler import extract_text_from_file, generate_docx, generate_pdf
from dotenv import load_dotenv
from google import genai
from pinecone import Pinecone
from langchain_text_splitters import RecursiveCharacterTextSplitter

load_dotenv()

# --- INICIALIZAÇÃO TÉCNICA ---
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME")

client_genai = None
index_pinecone = None

if GOOGLE_API_KEY: client_genai = genai.Client(api_key=GOOGLE_API_KEY)
if PINECONE_API_KEY and PINECONE_INDEX_NAME:
    pc = Pinecone(api_key=PINECONE_API_KEY)
    index_pinecone = pc.Index(PINECONE_INDEX_NAME)

def get_embedding(text):
    try:
        if not client_genai: return [0.0] * 768
        res = client_genai.models.embed_content(model="models/gemini-embedding-001", contents=text.replace('\x00', '').strip())
        return res.embeddings[0].values[:768]
    except: return [0.0]*768

def clean_filename(text):
    nfkd_form = unicodedata.normalize('NFKD', text)
    only_ascii = nfkd_form.encode('ASCII', 'ignore').decode('ASCII')
    return re.sub(r'[^a-zA-Z0-9_.]', '', only_ascii)

def get_base64_of_bin_file(bin_file):
    try:
        with open(bin_file, 'rb') as f: data = f.read()
        return base64.b64encode(data).decode()
    except: return None

def extract_title_from_story(story_text):
    if not story_text: return ""
    lines = story_text.strip().split('\n')
    potential_title = lines[0]
    for line in lines:
        clean = line.replace('#', '').replace('*', '').strip()
        if clean.lower().startswith("título:") or clean.lower().startswith("assunto:"):
            potential_title = clean.split(':')[-1].strip()
            break
        elif len(clean) > 5:
            potential_title = clean
            break
    return potential_title.replace('#', '').replace('*', '').strip()[:100]

def fetch_pinecone_context(query: str) -> str:
    """Busca o contexto na Pinecone antes de acionar os Agentes"""
    if not index_pinecone: return ""
    try:
        vector = get_embedding(query)
        search_result = index_pinecone.query(vector=vector, top_k=5, include_metadata=True)
        if not search_result['matches'] or search_result['matches'][0]['score'] < 0.35:
            return ""
        
        context_blocks = []
        for m in search_result['matches']:
            if 'text' in m['metadata']:
                source = m['metadata'].get('source', 'Documento Desconhecido')
                context_blocks.append(f"[{source}]: {m['metadata']['text']}")
        return "\n\n---\n\n".join(context_blocks)
    except Exception as e:
        print(f"Erro ao buscar contexto Pinecone: {e}")
        return ""

def main():
    st.set_page_config(page_title="CWS PM Assistant", page_icon="🚀", layout="wide", initial_sidebar_state="collapsed")
    try:
        with open("style.css") as f: st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except: pass

    @st.cache_data(ttl=3600)
    def load_jira_data():
        if os.getenv("JIRA_SERVER_URL"): return get_jira_projects(), get_jira_priorities()
        return {}, []

    projects, priorities = load_jira_data()
    if not projects: projects = {"CWS": "CWS Default"}
    if not priorities: priorities = ["High", "Medium", "Low"]

    # --- CABEÇALHO ---
    col_h1, col_h2 = st.columns([3, 1]) 
    with col_h1:
        st.markdown("# 🚀 CWS PM Assistant")
        st.markdown("##### Seu copiloto para transformar Discovery em Histórias de Usuário técnicas.")
    with col_h2:
        img_base = get_base64_of_bin_file("logo-preto-platform.png")
        if img_base:
            st.markdown(f'<div style="text-align: right;"><img src="data:image/png;base64,{img_base}" width="180"></div>', unsafe_allow_html=True)

    st.divider()
    tab_gen, tab_knowledge = st.tabs(["✍️ Gerador de Histórias", "📚 Base de Conhecimento"])

    # --- ABA: BASE DE CONHECIMENTO ---
    with tab_knowledge:
        st.markdown("### 📚 Gestão da Base de Dados")
        with st.container(border=True):
            rag_files = st.file_uploader("Suba manuais técnicos", accept_multiple_files=True, key="admin_rag")
            if st.button("🧠 Sincronizar Base de Dados", type="primary"):
                if rag_files and index_pinecone:
                    for f in rag_files:
                        with st.status(f"Processando {f.name}...") as status:
                            text = extract_text_from_file(f)
                            chunks = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200).split_text(text)
                            
                            # --- CORREÇÃO: TRATAMENTO DE ERRO EXPLÍCITO ---
                            try:
                                batch_size = 50
                                vectors = []
                                safe_namespace = clean_filename(f.name) # Força nome limpo para o Pinecone
                                
                                for i, c in enumerate(chunks):
                                    vectors.append({
                                        "id": f"{safe_namespace}_{i}", 
                                        "values": get_embedding(c), 
                                        "metadata": {"text": c, "source": f.name}
                                    })
                                    if len(vectors) >= batch_size:
                                        index_pinecone.upsert(vectors=vectors, namespace=safe_namespace)
                                        vectors = []
                                        time.sleep(0.5) # Pausa de 0.5s para não tomar rate limit
                                
                                if vectors:
                                    index_pinecone.upsert(vectors=vectors, namespace=safe_namespace)

                                status.update(label=f"✅ {f.name} integrado!", state="complete")
                            except Exception as e:
                                status.update(label=f"❌ Erro ao enviar {f.name}", state="error")
                                st.error(f"Erro detalhado do Pinecone: {str(e)}") # <- ISSO VAI MOSTRAR O MOTIVO REAL
                            # ---------------------------------------------------

                    st.rerun()
        st.markdown("#### 📄 Documentos Inseridos")
        if index_pinecone:
            try:
                stats = index_pinecone.describe_index_stats()
                for ns_name, ns_info in stats.get('namespaces', {}).items():
                    with st.container(border=True):
                        c1, c2, c3 = st.columns([4, 2, 1])
                        c1.markdown(f"**Arquivo:** `{ns_name}`")
                        c2.markdown(f"**Fragmentos:** {ns_info['vector_count']}")
                        if c3.button("🗑️", key=f"del_{ns_name}"):
                            index_pinecone.delete(delete_all=True, namespace=ns_name)
                            st.rerun()
            except: pass

    # --- ABA: GERADOR ---
    with tab_gen:
        st.markdown("### 1. 📥 Ingestão de Contexto")
        input_container = st.container(border=True)
        final_input_text = ""
        with input_container:
            sub1, sub2 = st.tabs(["📝 Digitar Contexto", "📂 Upload de Arquivo Único"])
            with sub1: manual_text = st.text_area("Descreva a necessidade:", height=200, key="manual_in")
            with sub2:
                up_file = st.file_uploader("Documento de input", type=["docx", "pdf", "txt", "md"], key="file_in")
                if up_file:
                    ext = extract_text_from_file(up_file)
                    final_input_text = f"ARQUIVO: {ext}\n\nNOTAS: {manual_text}"
                else: final_input_text = manual_text

        if st.button("✨ GERAR HISTÓRIA DE USUÁRIO", type="primary", use_container_width=True):
            if len(final_input_text) > 10:
                with st.spinner("🤖 Consultando Base e Inicializando Agentes..."):
                    
                    pinecone_context = fetch_pinecone_context(final_input_text)
                    
                    if pinecone_context:
                        enriched_input = (
                            f"NECESSIDADE DO USUÁRIO:\n{final_input_text}\n\n"
                            f"REGRAS TÉCNICAS E CONTEXTO OBRIGATÓRIO (Base CWS):\n{pinecone_context}\n\n"
                            "ATENÇÃO: Use obrigatoriamente as regras acima para gerar a história."
                        )
                        st.toast("✅ Base de conhecimento localizada e injetada no contexto!")
                    else:
                        enriched_input = final_input_text
                        st.toast("ℹ️ Nenhuma regra técnica extra encontrada na Base.", icon="ℹ️")

                    agents = CWSCrewAgents(GOOGLE_API_KEY, "gemini-2.0-flash")
                    tasks = CWSCrewTasks()
                    t1 = tasks.analysis_task(agents.context_interpreter_agent(), enriched_input)
                    t2 = tasks.drafting_task(agents.story_architect_agent(), [t1])
                    t3 = tasks.publication_task(agents.gatekeeper_agent(), [t2], "CWS")
                    crew = Crew(agents=[agents.context_interpreter_agent(), agents.story_architect_agent(), agents.gatekeeper_agent()], tasks=[t1, t2, t3], process=Process.sequential)
                    result = crew.kickoff()
                    st.session_state['story'], st.session_state['outputs'] = result.raw, [t1.output.raw, t2.output.raw]
                    st.session_state['auto_title'] = extract_title_from_story(result.raw)

        if 'story' in st.session_state:
            st.divider()
            st.markdown("### 2. 💎 Refinamento e Entrega")
            edited = st.text_area("Editor da História", value=st.session_state['story'], height=450)
            
            st.markdown("#### 🧠 Inteligência dos Agentes")
            col_i1, col_i2 = st.columns(2)
            with col_i1:
                with st.expander("🔍 Ver Análise Técnica"): st.markdown(st.session_state['outputs'][0])
            with col_i2:
                with st.expander("📝 Ver Rascunho Inicial"): st.markdown(st.session_state['outputs'][1])

            st.markdown("<br>", unsafe_allow_html=True)
            with st.container(border=True):
                st.markdown("#### 💾 Exportar")
                cd1, cd2, cd3 = st.columns(3)
                cd1.download_button("📄 DOCX", data=generate_docx(edited), file_name="historia.docx", use_container_width=True)
                cd2.download_button("📕 PDF", data=generate_pdf(edited), file_name="historia.pdf", use_container_width=True)
                cd3.download_button("📝 TXT", data=edited, file_name="historia.txt", use_container_width=True)

            # --- BLOCO JIRA ---
            with st.container(border=True):
                st.markdown("### 🚀 Publicar no Jira")
                jc1, jc2 = st.columns([3, 2])
                with jc1: t_title = st.text_input("1. Resumo (Título) *", value=st.session_state.get('auto_title', ""))
                with jc2:
                    squad = st.selectbox("2. Espaço (Squad) *", options=list(projects.keys()), format_func=lambda k: f"{k} - {projects[k]}", index=None, placeholder="Selecione a Squad...")
                
                meta = get_project_custom_fields_meta(squad) if squad else {}
                jc3, jc4, jc5 = st.columns(3)
                with jc3: pri = st.selectbox("3. Prioridade *", priorities, index=None, placeholder="Selecione a Prioridade...")
                with jc4: cli = st.selectbox("4. Cliente / Sponsor *", options=meta.get("client", {}).get("options", []), index=None, placeholder="Selecione o Cliente...", disabled=(not squad))
                with jc5: par = st.radio("5. Parametrização? *", meta.get("param", {}).get("allowed_values", ["Sim", "Não"]), horizontal=True)

                if st.button("Confirmar e Criar Ticket Jira ➔", type="primary", use_container_width=True):
                    tid, tlink = create_jira_issue_manual(squad, t_title, edited, pri, cli, par, meta)
                    if tid:
                        st.balloons()
                        st.success(f"Ticket {tid} criado com sucesso!")
                        st.link_button("Abrir no Jira", tlink)

if __name__ == "__main__": main()