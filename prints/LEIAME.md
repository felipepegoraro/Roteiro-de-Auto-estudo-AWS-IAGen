# Prints

| Arquivo | Etapa | O que mostra |
|---|---|---|
| `Captura de tela_2026-11-14_15-31-32.png` | 0 | `docker compose ps` (floci healthy + ollama), `sts get-caller-identity` (000000000000) e `converse` respondendo |
| `Captura de tela_2026-11-14_15-31-56.png` | 4 | `dynamodb scan` da tabela `triagem`: baixa, alta, média, injeção → `revisao_humana` |
| `Captura de tela_2026-11-14_15-18-44.png` | 5 | agente, execução 5: aprovação `s` (rótulo antigo, com o erro descrito no diário) |
| `Captura de tela_2026-11-14_15-21-08.png` | 5 | agente, execução 6: negação `N` (rótulo antigo) |
| `Captura de tela_2026-11-14_15-27-22.png` | 5 | agente, execução 7: aprovação `s` → ASG para 3 (rótulo corrigido) |
| `Captura de tela_2026-11-14_15-29-30.png` | 5 | agente, execução 8: negação `N` (rótulo corrigido) |
