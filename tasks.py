from crewai import Task

class CWSCrewTasks:
    def analysis_task(self, agent, inputs):
        return Task(
            description=(
                f"1. Analise o input: {inputs}.\n"
                "2. Identifique: Objetivos, Personas e Riscos Técnicos.\n"
                "3. Use a WebSearch se precisar verificar documentação de API padrão.\n"
                "4. Responda em PORTUGUÊS."
            ),
            expected_output="Relatório Técnico de Discovery.",
            agent=agent
        )

    def drafting_task(self, agent, context):
        return Task(
            description=(
                "Escreva a História de Usuário baseada no relatório técnico.\n"
                "Estrutura: Título, Contexto, Objetivo, Critérios de Aceite (Gherkin).\n"
                "Tom: Executivo e Pragmático."
            ),
            expected_output="História de Usuário formatada em Markdown.",
            context=context,
            agent=agent
        )

    def publication_task(self, agent, context, project_key):
        return Task(
            description=(
                f"Revise a história para o projeto '{project_key}'. "
                "Garanta que esteja pronta para ser copiada para o Jira."
            ),
            expected_output="Conteúdo Final Refinado em Português.",
            context=context,
            agent=agent
        )