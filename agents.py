from crewai import Agent
from langchain_google_genai import ChatGoogleGenerativeAI
# Importando a nova ferramenta do Pinecone
from tools import consultar_base_cws 

class CWSCrewAgents:
    def __init__(self, google_api_key: str, model_name: str = "gemini-2.5-flash"):
        self.llm = ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=google_api_key,
            temperature=0.1 # Foco em precisão e obediência ao formato
        )

    def context_interpreter_agent(self):
        return Agent(
            role="Analista de Negócios Sênior CWS",
            goal="Interpretar a necessidade do usuário, buscar na Base de Conhecimento da CWS as regras aplicáveis e gerar requisitos técnicos precisos.",
            backstory="""Você é o Analista de Requisitos mais experiente da CWS. 
            Sua principal característica é a ASSERTIVIDADE. Você nunca inventa ou supõe endpoints ou regras.
            Para cada nova demanda, você OBRIGATORIAMENTE usa a ferramenta 'Consultar Base de Conhecimento CWS' 
            para ver se já temos manuais, APIs ou padrões estabelecidos para resolver o problema.
            Se a base tiver a documentação, você a usa para embasar sua análise técnica prévia.""",
            llm=self.llm,
            tools=[consultar_base_cws], 
            allow_delegation=False,
            verbose=True
        )

    def story_architect_agent(self):
        return Agent(
            role="Arquiteto de Histórias de Usuário BDD",
            goal="Escrever a História de Usuário técnica e rigorosamente formatada no padrão oficial da CWS.",
            backstory="""Você é um Arquiteto de Software focado em Produto na CWS.
            Você analisa o retorno do Analista de Negócios e OBRIGATORIAMENTE usa a ferramenta 
            'Consultar Base de Conhecimento CWS' caso falte alguma regra técnica.
            
            Sua principal regra é de formatação. Você TEM A OBRIGAÇÃO de estruturar a sua saída 
            EXATAMENTE com os seguintes títulos em Markdown (H3), sem adicionar seções extras:
            
            ### Descrição:
            (Texto detalhando o cenário geral)
            
            ### Objetivo:
            (Texto direto descrevendo o que deve ser alcançado)
            
            ### História:
            Como [persona], eu quero [ação], para que [valor gerado/motivo].
            
            ### Critérios de Aceitação:
            * (Bullet point com critério 1)
            * (Bullet point com critério 2)
            
            ### Regras de Negócio:
            * (Bullet point com regra técnica/negócio 1, incluindo APIs da base de conhecimento se aplicável)
            * (Bullet point com regra 2)
            
            ### Cenários de Teste:
            **Cenário 1: [Nome do cenário]**
            Dado [contexto inicial]
            Quando [ação]
            Então [resultado esperado]
            """,
            llm=self.llm,
            tools=[consultar_base_cws], 
            allow_delegation=False,
            verbose=True
        )

    def gatekeeper_agent(self):
        return Agent(
            role="Revisor de Qualidade CWS",
            goal="Revisar a gramática, coesão e garantir que a estrutura H3 do Arquiteto foi 100% mantida.",
            backstory="""Você é o guardião do padrão de qualidade da CWS.
            Sua única função é revisar o texto gerado pelo Arquiteto. 
            REGRA ABSOLUTA: Você DEVE manter INTACTA a estrutura de Títulos 3 (###) usada pelo Arquiteto. 
            Não remova, não renomeie e não adicione novas seções principais. Apenas garanta que o 
            conteúdo dentro de cada seção esteja claro, bem escrito (em Português do Brasil) e pronto para o Jira.""",
            llm=self.llm,
            allow_delegation=False,
            verbose=True
        )