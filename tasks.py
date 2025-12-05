from crewai import Task

class CWSCrewTasks:
    def analysis_task(self, agent, inputs):
        return Task(
            description=(
                f"1. Analise o input: {inputs}.\n"
                "2. Identifique: Objetivos, Personas e Riscos Técnicos.\n"
                "3. Responda estritamente em PORTUGUÊS DO BRASIL."
            ),
            expected_output="Relatório Técnico de Discovery em PT-BR.",
            agent=agent
        )

    def drafting_task(self, agent, context):
        return Task(
            description=(
                "Escreva a História de Usuário baseada no relatório técnico.\n"
                "Estrutura: Título, Contexto, Objetivo, Critérios de Aceite (Gherkin).\n"
                "IMPORTANTE: O Título deve ser claro, objetivo e ter NO MÁXIMO 100 caracteres.\n"
                "Idioma Obrigatório: PORTUGUÊS DO BRASIL."
            ),
            expected_output="História de Usuário formatada em Markdown (PT-BR).",
            context=context,
            agent=agent
        )

    def publication_task(self, agent, context, project_key):
        return Task(
            description=(
                f"Revise a história para o projeto '{project_key}'. "
                "Garanta que esteja pronta para ser copiada para o Jira. "
                "Certifique-se de que NÃO HÁ NENHUMA PALAVRA EM INGLÊS no pensamento ou no texto final."
            ),
            expected_output="Conteúdo Final Refinado em Português do Brasil.",
            context=context,
            agent=agent
        )