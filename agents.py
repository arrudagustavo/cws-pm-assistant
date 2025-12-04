from crewai import Agent, LLM
from crewai_tools import FileReadTool, ScrapeWebsiteTool
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

        self.file_tool = FileReadTool()
        self.web_tool = ScrapeWebsiteTool() 

    def context_interpreter_agent(self):
        return Agent(
            role='Analista Técnico de Produto Sênior',
            goal='Analisar inputs brutos e validar viabilidade técnica.',
            backstory=(
                "Você é Analista na CWS. Seu foco é detectar riscos de integração e quebras de API. "
                "Você deve estruturar o problema de negócio de forma lógica."
            ),
            tools=[self.file_tool, self.web_tool],
            llm=self.llm,
            verbose=True
        )

    def story_architect_agent(self):
        return Agent(
            role='PM Sênior - Jornada Unificada',
            goal='Escrever a História de Usuário em Markdown.',
            backstory=(
                "Você escreve histórias detalhadas. Você foca na experiência unificada (Vendedor + Cliente). "
                "Seu texto é elegante, claro e segue o padrão Gherkin nos critérios."
            ),
            tools=[self.file_tool],
            llm=self.llm,
            verbose=True
        )

    def gatekeeper_agent(self):
        return Agent(
            role='Head de Produto (Revisor)',
            goal='Revisar e refinar a história final.',
            backstory=(
                "Você garante a qualidade. Verifica se o tom é executivo e se não há pontas soltas. "
                "Você prepara o texto final para ser publicado."
            ),
            tools=[],
            llm=self.llm,
            verbose=True
        )