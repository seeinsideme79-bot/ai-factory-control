# Orchestration Rules v1.0

## Temel Prensipler

1. **State-first**: Tüm kararlar state.yaml'a dayanır
2. **Human-in-the-loop**: Kritik geçişlerde insan onayı
3. **No memory**: Agent'lar sohbet geçmişine dayanmaz
4. **Single responsibility**: Her agent tek iş yapar

## Phase Transitions
```
idea ──[vizyon]──> prp ──[onay]──> development ──[kod]──> test
                                        ^                   │
                                        │                   v
                                   [revizyon] <── human_validation
                                                        │
                                                        v
                                                     release
```

## Trigger Rules

### Automatic Triggers
- `test_agent` → `dev_agent` (test failure)
- `doc_agent` tetikleme (her code commit sonrası)

### Human Approval Required
- `idea` → `prp` (vizyon onayı)
- `prp` → `development` (PRP onayı)
- `test` → `human_validation` (test geçişi)
- `human_validation` → `release` (final onay)

## Blocking Rules

### Block Conditions
- Test failure: `blocking.reason = test_failure`
- Awaiting human: `blocking.reason = awaiting_human`
- Agent error: `blocking.reason = agent_error`

### Unblock Conditions
- Test fix: `health.test_pass_rate = 1.0`
- Human response: explicit approval in dashboard
- Error resolution: manual intervention

## Revision Limits

- Max revision count: 5
- After limit: escalate to human
- Reset on phase change

## Automation Mode

Eğer `automation.allowed = true`:
- `auto_agents` listesindeki agent'lar otomatik çalışır
- Human approval gerektiren geçişler hariç
