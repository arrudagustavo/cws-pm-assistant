from crewai import Agent, LLM
from crewai_tools import ScrapeWebsiteTool
from tools import CreateJiraTicketTool
import os

class CWSCrewAgents:
    def __init__(self, google_api_key, model_name="gemini-2.5-flash"):
        os.environ["GOOGLE_API_KEY"] = google_api_key
        
        # Configuração do Modelo
        self.llm = LLM(
            model=f"gemini/{model_name}",
            temperature=0.7
        )

        # REMOVIDO: self.file_tool = FileReadTool() (Causava o erro)
        self.web_tool = ScrapeWebsiteTool() 

    def context_interpreter_agent(self):
        return Agent(
            role='Analista Técnico de Produto Sênior',
            goal='Analisar inputs brutos e validar viabilidade técnica em Português.',
            backstory=(
                "Você é Analista na CWS. Seu foco é detectar riscos de integração e quebras de API. "
                "Você deve estruturar o problema de negócio de forma lógica. "
                "Você recebe o CONTEXTO COMPLETO já extraído. Não tente ler arquivos externos."
                "\n\n🚨 REGRA DE OURO: Você deve PENSAR (Thought), RACIOCINAR e ESCREVER estritamente em PORTUGUÊS DO BRASIL (PT-BR). "
                "Jamais gere texto ou pensamentos em Inglês."
            ),
            # Apenas Web Tool, sem File Tool
            tools=[self.web_tool],
            llm=self.llm,
            verbose=True
        )

    def story_architect_agent(self):
        return Agent(
            role='PM Sênior - Jornada Unificada',
            goal='Escrever a História de Usuário em Markdown (PT-BR).',
            backstory=(
                "Você escreve histórias detalhadas. Você foca na experiência unificada (Vendedor + Cliente). "
                "Seu texto é elegante, claro e segue o padrão Gherkin nos critérios. "
                "\n\n🚨 REGRA DE OURO: Todo o seu output e raciocínio devem ser em PORTUGUÊS DO BRASIL. "
                "Traduza qualquer termo técnico que não seja padrão de mercado."
            ),
            tools=[], # Sem tools, foco total na escrita
            llm=self.llm,
            verbose=True
        )

    def gatekeeper_agent(self):
        return Agent(
            role='Head de Produto (Revisor)',
            goal='Revisar e refinar a história final em Português.',
            backstory=(
                "Você garante a qualidade. Verifica se o tom é executivo e se não há pontas soltas. "
                "Você prepara o texto final para ser publicado. "
                "\n\n🚨 REGRA DE OURO: Pense e responda 100% em PORTUGUÊS DO BRASIL. "
                "Garanta que não sobrou nenhum trecho em inglês do agente anterior."
            ),
            tools=[],
            llm=self.llm,
            verbose=True
        )