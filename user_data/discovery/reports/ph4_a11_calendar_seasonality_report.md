# PH4-A11 - Calendar Seasonality

Generated: `2026-07-14T19:51:42.007241+00:00`

**Decision:** OHLCV CALENDAR-SEASONALITY HYPOTHESIS REJECTED IN PRIMARY SCOPE

No fixed contrast passed every pre-registered P1 gate on valid data.

## Frozen protocol

- Eleven fixed contrasts; hourly HH:00 UTC observations; one 60-minute horizon.
- Conservative round-trip cost 0.30%; 60/40 chronological split and 12-candle embargo.
- 1,000 complete-UTC-week bootstrap replicates; no label selection or ranking.

## Contrasts

### MONDAY

- Net mean/median 0.30%: `-0.003449744817976435` / `-0.003211281328203149`; mean CI95 `[-0.00423631037307678, -0.00423631037307678]`
- Return beta/effect: `-0.0002485437799540946` / `-0.00028697562178521`
- Return MSE/MAE improvement: `-0.008174513478552697` / `-0.0026696645062944157`
- Positive pairs/blocks: `0/10`, `0/5`
- P1 Holm: `{'return_net_mean_conservative': 1.0, 'return_effect': 1.0, 'return_mse_improvement': 1.0, 'return_mae_improvement': 1.0, 'return_circular_mse_superiority': 0.0, 'return_week_permutation_mse_superiority': 0.0, 'return_reverse_time_mse_superiority': 1.0, 'return_beta': 1.0}`
- Risk beta, MSE, MAE: `0.0009090893523630922`, `-0.002951722404520869`, `-0.00295903625674808`
- P2 Holm: `{'risk_mse_improvement': 1.0, 'risk_mae_improvement': 1.0, 'risk_circular_mse_superiority': 1.0, 'risk_week_permutation_mse_superiority': 1.0, 'risk_reverse_time_mse_superiority': 1.0, 'risk_beta': 7.934373158491326e-09}`
- Passes all P1 gates: `False`

### TUESDAY

- Net mean/median 0.30%: `-0.003086639752496065` / `-0.0034864047465892906`; mean CI95 `[-0.0032534506591862062, -0.0032534506591862062]`
- Return beta/effect: `-8.035268039406732e-06` / `0.0001287267150133357`
- Return MSE/MAE improvement: `1.283057459221748e-05` / `-0.0023148798269511128`
- Positive pairs/blocks: `0/10`, `0/5`
- P1 Holm: `{'return_net_mean_conservative': 1.0, 'return_effect': 1.0, 'return_mse_improvement': 0.0, 'return_mae_improvement': 1.0, 'return_circular_mse_superiority': 0.0, 'return_week_permutation_mse_superiority': 0.0, 'return_reverse_time_mse_superiority': 0.0, 'return_beta': 1.0}`
- Risk beta, MSE, MAE: `0.0009417132755051572`, `0.0019813672815408843`, `0.00097573064879797`
- P2 Holm: `{'risk_mse_improvement': 0.0, 'risk_mae_improvement': 0.0, 'risk_circular_mse_superiority': 0.0, 'risk_week_permutation_mse_superiority': 0.0, 'risk_reverse_time_mse_superiority': 0.0, 'risk_beta': 2.0048368520875215e-09}`
- Passes all P1 gates: `False`

### WEDNESDAY

- Net mean/median 0.30%: `-0.0027235248127445238` / `-0.002770503553328573`; mean CI95 `[-0.0022673073958492324, -0.0022673073958492324]`
- Return beta/effect: `0.00030484378263866076` / `0.0005505268975530045`
- Return MSE/MAE improvement: `-0.005215442303019981` / `-0.003352382842967758`
- Positive pairs/blocks: `0/10`, `0/5`
- P1 Holm: `{'return_net_mean_conservative': 1.0, 'return_effect': 0.0, 'return_mse_improvement': 1.0, 'return_mae_improvement': 1.0, 'return_circular_mse_superiority': 1.0, 'return_week_permutation_mse_superiority': 1.0, 'return_reverse_time_mse_superiority': 1.0, 'return_beta': 0.7722258214821982}`
- Risk beta, MSE, MAE: `0.0002354943196260234`, `-0.0009886518453530702`, `-0.0004302744297024086`
- P2 Holm: `{'risk_mse_improvement': 1.0, 'risk_mae_improvement': 1.0, 'risk_circular_mse_superiority': 1.0, 'risk_week_permutation_mse_superiority': 0.0, 'risk_reverse_time_mse_superiority': 0.0, 'risk_beta': 1.0}`
- Passes all P1 gates: `False`

### THURSDAY

- Net mean/median 0.30%: `-0.003626165342465683` / `-0.003235756479037846`; mean CI95 `[-0.0030650313410964585, -0.0030650313410964585]`
- Return beta/effect: `-0.0007545503313809557` / `-0.0005000792049035641`
- Return MSE/MAE improvement: `-0.0029152970774427222` / `-0.001962378535588092`
- Positive pairs/blocks: `0/10`, `0/5`
- P1 Holm: `{'return_net_mean_conservative': 1.0, 'return_effect': 0.0, 'return_mse_improvement': 1.0, 'return_mae_improvement': 1.0, 'return_circular_mse_superiority': 1.0, 'return_week_permutation_mse_superiority': 1.0, 'return_reverse_time_mse_superiority': 0.0, 'return_beta': 1.0}`
- Risk beta, MSE, MAE: `0.000397891675724702`, `-0.0003522045249770622`, `-0.0009735292845880328`
- P2 Holm: `{'risk_mse_improvement': 1.0, 'risk_mae_improvement': 1.0, 'risk_circular_mse_superiority': 1.0, 'risk_week_permutation_mse_superiority': 0.0, 'risk_reverse_time_mse_superiority': 1.0, 'risk_beta': 0.08270440517980582}`
- Passes all P1 gates: `False`

### FRIDAY

- Net mean/median 0.30%: `-0.003064701057253738` / `-0.002847352019846882`; mean CI95 `[-0.0028509169970353226, -0.0028509169970353226]`
- Return beta/effect: `-0.00035128497377654935` / `0.00013604648503684222`
- Return MSE/MAE improvement: `-0.007786223623630873` / `-0.004181234008996753`
- Positive pairs/blocks: `0/10`, `0/5`
- P1 Holm: `{'return_net_mean_conservative': 1.0, 'return_effect': 0.0, 'return_mse_improvement': 1.0, 'return_mae_improvement': 1.0, 'return_circular_mse_superiority': 0.0, 'return_week_permutation_mse_superiority': 0.0, 'return_reverse_time_mse_superiority': 0.0, 'return_beta': 1.0}`
- Risk beta, MSE, MAE: `0.0008958950770044427`, `-0.004936267104191257`, `-0.0033326772203604318`
- P2 Holm: `{'risk_mse_improvement': 1.0, 'risk_mae_improvement': 1.0, 'risk_circular_mse_superiority': 1.0, 'risk_week_permutation_mse_superiority': 1.0, 'risk_reverse_time_mse_superiority': 1.0, 'risk_beta': 1.1274056799237542e-08}`
- Passes all P1 gates: `False`

### SATURDAY

- Net mean/median 0.30%: `-0.0030475648811436147` / `-0.0030426199715281716`; mean CI95 `[-0.0031918628146053495, -0.0031918628146053495]`
- Return beta/effect: `0.0003328544395460449` / `0.00017816787835268083`
- Return MSE/MAE improvement: `-0.002215471465972474` / `-0.0008343556788736195`
- Positive pairs/blocks: `0/10`, `0/5`
- P1 Holm: `{'return_net_mean_conservative': 1.0, 'return_effect': 1.0, 'return_mse_improvement': 1.0, 'return_mae_improvement': 1.0, 'return_circular_mse_superiority': 1.0, 'return_week_permutation_mse_superiority': 1.0, 'return_reverse_time_mse_superiority': 0.0, 'return_beta': 0.4677619798548599}`
- Risk beta, MSE, MAE: `-0.002038806692998063`, `0.01535081228872333`, `0.013367631800005173`
- P2 Holm: `{'risk_mse_improvement': 0.0, 'risk_mae_improvement': 0.0, 'risk_circular_mse_superiority': 0.0, 'risk_week_permutation_mse_superiority': 0.0, 'risk_reverse_time_mse_superiority': 0.0, 'risk_beta': 1.0}`
- Passes all P1 gates: `False`

### SUNDAY

- Net mean/median 0.30%: `-0.0033246012949619637` / `-0.0032527233936943817`; mean CI95 `[-0.003468875230367388, -0.003468875230367388]`
- Return beta/effect: `0.0007414683513231382` / `-0.00014905381447128912`
- Return MSE/MAE improvement: `-0.0016339640666736298` / `-0.002229149584175354`
- Positive pairs/blocks: `0/10`, `0/5`
- P1 Holm: `{'return_net_mean_conservative': 1.0, 'return_effect': 1.0, 'return_mse_improvement': 1.0, 'return_mae_improvement': 1.0, 'return_circular_mse_superiority': 0.0, 'return_week_permutation_mse_superiority': 0.0, 'return_reverse_time_mse_superiority': 0.0, 'return_beta': 1.4819221547668349e-06}`
- Risk beta, MSE, MAE: `-0.0013644497238660363`, `0.0014040538122483159`, `-0.0004694789587632564`
- P2 Holm: `{'risk_mse_improvement': 1.0, 'risk_mae_improvement': 1.0, 'risk_circular_mse_superiority': 0.0, 'risk_week_permutation_mse_superiority': 0.0, 'risk_reverse_time_mse_superiority': 0.0, 'risk_beta': 1.0}`
- Passes all P1 gates: `False`

### WEEKEND

- Net mean/median 0.30%: `-0.0031933987966185377` / `-0.0031042534060612254`; mean CI95 `[-0.0033303690224863692, -0.0033303690224863692]`
- Return beta/effect: `0.0006612711933901907` / `1.3527966528397186e-05`
- Return MSE/MAE improvement: `-0.004064963532498884` / `-0.0015522391556056613`
- Positive pairs/blocks: `0/10`, `0/5`
- P1 Holm: `{'return_net_mean_conservative': 1.0, 'return_effect': 1.0, 'return_mse_improvement': 1.0, 'return_mae_improvement': 1.0, 'return_circular_mse_superiority': 0.0, 'return_week_permutation_mse_superiority': 0.0, 'return_reverse_time_mse_superiority': 1.0, 'return_beta': 3.2755407275431025e-08}`
- Risk beta, MSE, MAE: `-0.00217633057331512`, `0.020149351064332556`, `0.014467910144328761`
- P2 Holm: `{'risk_mse_improvement': 0.0, 'risk_mae_improvement': 0.0, 'risk_circular_mse_superiority': 0.0, 'risk_week_permutation_mse_superiority': 0.0, 'risk_reverse_time_mse_superiority': 0.0, 'risk_beta': 1.0}`
- Passes all P1 gates: `False`

### UTC_00_08

- Net mean/median 0.30%: `-0.0031320801940816333` / `-0.003237922105440831`; mean CI95 `[-0.003528841992050128, -0.003528841992050128]`
- Return beta/effect: `0.00014661853325956414` / `9.68020687207702e-05`
- Return MSE/MAE improvement: `-0.00030557396734390177` / `-0.00039182260634794684`
- Positive pairs/blocks: `0/10`, `0/5`
- P1 Holm: `{'return_net_mean_conservative': 1.0, 'return_effect': 1.0, 'return_mse_improvement': 1.0, 'return_mae_improvement': 1.0, 'return_circular_mse_superiority': 0.0, 'return_week_permutation_mse_superiority': 0.0, 'return_reverse_time_mse_superiority': 0.0, 'return_beta': 1.0}`
- Risk beta, MSE, MAE: `-0.0006532795935708612`, `0.002388968856550255`, `0.0005314356915194663`
- P2 Holm: `{'risk_mse_improvement': 0.0, 'risk_mae_improvement': 0.0, 'risk_circular_mse_superiority': 0.0, 'risk_week_permutation_mse_superiority': 0.0, 'risk_reverse_time_mse_superiority': 0.0, 'risk_beta': 1.0}`
- Passes all P1 gates: `False`

### UTC_08_16

- Net mean/median 0.30%: `-0.003174511995922966` / `-0.0032471955659702585`; mean CI95 `[-0.0032190530958696394, -0.0032190530958696394]`
- Return beta/effect: `-6.066173320053138e-05` / `3.4268010288656304e-05`
- Return MSE/MAE improvement: `-0.0028742809018243577` / `-0.0016670631790524637`
- Positive pairs/blocks: `0/10`, `0/5`
- P1 Holm: `{'return_net_mean_conservative': 1.0, 'return_effect': 1.0, 'return_mse_improvement': 1.0, 'return_mae_improvement': 1.0, 'return_circular_mse_superiority': 1.0, 'return_week_permutation_mse_superiority': 1.0, 'return_reverse_time_mse_superiority': 1.0, 'return_beta': 1.0}`
- Risk beta, MSE, MAE: `0.0015008628013110426`, `0.007010695589425027`, `0.0042853581094296775`
- P2 Holm: `{'risk_mse_improvement': 0.0, 'risk_mae_improvement': 0.0, 'risk_circular_mse_superiority': 0.0, 'risk_week_permutation_mse_superiority': 0.0, 'risk_reverse_time_mse_superiority': 0.0, 'risk_beta': 0.0}`
- Passes all P1 gates: `False`

### UTC_16_24

- Net mean/median 0.30%: `-0.0032809680646869064` / `-0.002869040599964893`; mean CI95 `[-0.0028237141168874057, -0.0028237141168874057]`
- Return beta/effect: `-8.458930587645805e-05` / `-0.00012748421834902557`
- Return MSE/MAE improvement: `-0.0038419997016058095` / `-0.0016571961079908948`
- Positive pairs/blocks: `0/10`, `0/5`
- P1 Holm: `{'return_net_mean_conservative': 1.0, 'return_effect': 0.0, 'return_mse_improvement': 1.0, 'return_mae_improvement': 1.0, 'return_circular_mse_superiority': 1.0, 'return_week_permutation_mse_superiority': 1.0, 'return_reverse_time_mse_superiority': 1.0, 'return_beta': 1.0}`
- Risk beta, MSE, MAE: `-0.0008613266418237891`, `0.0012305223643710383`, `0.0014415216438308897`
- P2 Holm: `{'risk_mse_improvement': 0.0, 'risk_mae_improvement': 0.0, 'risk_circular_mse_superiority': 1.0, 'risk_week_permutation_mse_superiority': 0.0, 'risk_reverse_time_mse_superiority': 1.0, 'risk_beta': 1.0}`
- Passes all P1 gates: `False`

## Integrity

- Integrity sufficient: `True`
- Informative units: `50`
- Protocol SHA-256: `5ff6e981a6af7d88c09c37398df2c55566f97c8d3305745e74f4ef7c135d157a`
- Operational experiment justified: `False`
