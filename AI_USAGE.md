# How I Used AI

Antes de começar qualquer projeto, procuro sempre compreender o problema, as regras de negócio e as possíveis soluções. Normalmente, este processo de análise e compreensão exige algum tempo, mas, neste projeto, tive um prazo mais limitado do que aquele a que estou habituado.

Por isso, a minha primeira decisão foi definir como iria utilizar a AI, tendo em conta as limitações de prompts e tokens disponíveis.

Decidi utilizar três ferramentas de AI, cada uma com uma função específica:

- **ChatGPT — Assistente e conselheiro:** foi a única ferramenta que teve conhecimento de todo o contexto do projeto, incluindo o desafio, as regras de negócio e os requisitos. Utilizei-a para apresentar o meu raciocínio, discutir decisões de arquitetura e modelação e obter feedback, garantindo que as soluções respeitavam todas as regras.
- **Claude Code — Implementador:** utilizei-o para implementar código com base nas instruções que lhe fornecia. A sua função era executar as tarefas solicitadas e deixar comentários quando necessário, sem tomar decisões de arquitetura ou de negócio por iniciativa própria. Sempre que o fazia, rejeitava essas alterações.
- **GitHub Copilot — Tester:** utilizei-o para analisar o código e ajudar na criação e execução de testes.

Embora tenha utilizado três ferramentas de AI, apenas uma tinha conhecimento do contexto completo do projeto: o ChatGPT. O Claude Code recebia instruções específicas para cada tarefa, enquanto o GitHub Copilot se concentrava na análise do código e nos testes.

Da minha parte, escrevi diretamente algumas partes do código, nomeadamente a API, a classe `Worker` e partes do `docker-compose.yml` e do `Makefile`.

No entanto, o desenho da arquitetura, a separação dos módulos, as decisões de modelação e as decisões técnicas foram da minha responsabilidade. Procurei utilizar a AI como uma ferramenta de apoio à implementação e validação, mantendo sempre o controlo sobre as decisões tomadas ao longo do desenvolvimento.