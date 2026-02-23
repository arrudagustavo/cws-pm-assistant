from crewai import Task

class CWSCrewTasks:
    def analysis_task(self, agent, inputs):
        return Task(
            description=(
                f"1. Analise a necessidade de negócio: {inputs}.\n"
                "2. Utilize a ferramenta 'Consultar Base de Conhecimento CWS' para buscar contexto, APIs, integrações ou regras de negócio relacionadas a essa demanda.\n"
                "3. Identifique: Objetivos principais, Personas envolvidas e Riscos/Dependências Técnicas.\n"
                "4. Responda estritamente em PORTUGUÊS DO BRASIL."
            ),
            expected_output="Relatório Técnico de Discovery em PT-BR, contendo o embasamento de negócio e as regras técnicas/APIs encontradas na base da CWS.",
            agent=agent
        )

    def drafting_task(self, agent, context):
        return Task(
            description=(
                "Escreva a História de Usuário baseada no relatório técnico da tarefa anterior.\n"
                "REGRA DE OURO: Você OBRIGATORIAMENTE deve usar APENAS a estrutura abaixo com Markdown H3 (###). Não crie subtítulos extras ou seções fora deste padrão:\n\n"
                "### Descrição:\n"
                "(Texto explicativo)\n\n"
                "### Objetivo:\n"
                "(Texto direto do que deve ser alcançado)\n\n"
                "### História:\n"
                "Como [persona], eu quero [ação], para que [valor gerado].\n\n"
                "### Critérios de Aceitação:\n"
                "* (Bullet points com os critérios)\n\n"
                "### Regras de Negócio:\n"
                "* (Bullet points com regras técnicas, limites e endpoints da base de conhecimento)\n\n"
                "### Cenários de Teste:\n"
                "(Use o formato Dado, Quando, Então para descrever os testes)\n\n"
                "Idioma Obrigatório: PORTUGUÊS DO BRASIL."
            ),
            expected_output="História de Usuário formatada em Markdown (PT-BR) usando RIGOROSAMENTE os 6 títulos H3 definidos.",
            context=context,
            agent=agent
        )

    def publication_task(self, agent, context, project_key):
        return Task(
            description=(
                f"Revise a história para o projeto '{project_key}'.\n"
                "1. Garanta que a estrutura de títulos H3 (Descrição, Objetivo, História, Critérios de Aceitação, Regras de Negócio, Cenários de Teste) não foi alterada, removida ou renomeada.\n"
                "2. Remova qualquer 'gordura' ou introdução desnecessária como 'Aqui está a história:' ou 'Claro, vou ajudar com isso'. O texto deve começar direto no primeiro título H3.\n"
                "3. Certifique-se de que NÃO HÁ NENHUMA PALAVRA EM INGLÊS no texto final, exceto termos técnicos inevitáveis (como API, Payload, Endpoint)."
            ),
            expected_output="Conteúdo Final Refinado e enxuto em Português do Brasil, mantendo os H3 intactos, pronto para cópia pro Jira.",
            context=context,
            agent=agent
        )