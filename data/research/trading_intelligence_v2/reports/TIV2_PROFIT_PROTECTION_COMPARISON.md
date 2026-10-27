# Original profit protection A/B

A: original source-default SL/TP geometry (20/40 pips). B: same geometry with unchanged original 67% activation, ATR14*0.5 giveback (original clamps 0.5..30 pips), 4-pip missing-ATR fallback and monotonic ratchet, BUY/SELL and JPY-aware. No alternative C is justified by this short sample. Completed-bar favorable extreme updates MFE; original protection compares executable close; requested software exit executes at the next open. SL/TP takes precedence. No retroactive favorable threshold fill and no broker trailing amendment. A completed-bar simulation cannot establish live monitoring equivalence.

- EUR_USD/scalp: A R=-0.128588, B R=-0.127404, B-A=0.001184; nA=201, nB=204.
- EUR_USD/trend: A R=-0.129090, B R=-0.127899, B-A=0.001191; nA=201, nB=204.
- EUR_USD/mean_reversion: A R=-0.103745, B R=-0.093577, B-A=0.010168; nA=95, nB=97.
- EUR_USD/swing_trend: A R=-0.142892, B R=-0.142438, B-A=0.000454; nA=176, nB=177.
- EUR_USD/swing_mean_reversion: A R=-0.122130, B R=-0.120192, B-A=0.001937; nA=67, nB=67.
- EUR_USD/swing_breakout: A R=-0.176481, B R=-0.176366, B-A=0.000114; nA=113, nB=114.
- GBP_USD/scalp: A R=-0.183997, B R=-0.184214, B-A=-0.000217; nA=199, nB=199.
- GBP_USD/trend: A R=-0.181798, B R=-0.182016, B-A=-0.000217; nA=199, nB=199.
- GBP_USD/mean_reversion: A R=-0.101164, B R=-0.094000, B-A=0.007164; nA=95, nB=96.
- GBP_USD/swing_trend: A R=-0.198199, B R=-0.197779, B-A=0.000421; nA=173, nB=174.
- GBP_USD/swing_mean_reversion: A R=-0.068590, B R=-0.069648, B-A=-0.001059; nA=75, nB=76.
- GBP_USD/swing_breakout: A R=-0.236896, B R=-0.230386, B-A=0.006510; nA=113, nB=113.
- USD_JPY/scalp: A R=-0.164932, B R=-0.169920, B-A=-0.004988; nA=213, nB=220.
- USD_JPY/trend: A R=-0.162928, B R=-0.167122, B-A=-0.004194; nA=213, nB=220.
- USD_JPY/mean_reversion: A R=-0.013555, B R=-0.038281, B-A=-0.024726; nA=97, nB=99.
- USD_JPY/swing_trend: A R=-0.197693, B R=-0.200956, B-A=-0.003262; nA=186, nB=193.
- USD_JPY/swing_mean_reversion: A R=-0.042029, B R=-0.053884, B-A=-0.011855; nA=71, nB=71.
- USD_JPY/swing_breakout: A R=-0.149641, B R=-0.148604, B-A=0.001037; nA=110, nB=112.
- AUD_USD/scalp: A R=-0.120951, B R=-0.120951, B-A=0.000000; nA=190, nB=190.
- AUD_USD/trend: A R=-0.123691, B R=-0.123691, B-A=0.000000; nA=191, nB=191.
- AUD_USD/mean_reversion: A R=-0.100962, B R=-0.093935, B-A=0.007027; nA=89, nB=91.
- AUD_USD/swing_trend: A R=-0.177856, B R=-0.176263, B-A=0.001593; nA=168, nB=169.
- AUD_USD/swing_mean_reversion: A R=-0.046823, B R=-0.056787, B-A=-0.009964; nA=69, nB=69.
- AUD_USD/swing_breakout: A R=-0.099634, B R=-0.096381, B-A=0.003253; nA=105, nB=106.
- USD_CAD/scalp: A R=-0.159847, B R=-0.161841, B-A=-0.001994; nA=195, nB=196.
- USD_CAD/trend: A R=-0.163770, B R=-0.165744, B-A=-0.001974; nA=195, nB=196.
- USD_CAD/mean_reversion: A R=-0.159682, B R=-0.144051, B-A=0.015631; nA=93, nB=94.
- USD_CAD/swing_trend: A R=-0.166592, B R=-0.170723, B-A=-0.004132; nA=178, nB=179.
- USD_CAD/swing_mean_reversion: A R=-0.110460, B R=-0.088376, B-A=0.022084; nA=70, nB=71.
- USD_CAD/swing_breakout: A R=-0.154639, B R=-0.154639, B-A=0.000000; nA=117, nB=117.
- USD_CHF/scalp: A R=-0.208154, B R=-0.211768, B-A=-0.003614; nA=192, nB=194.
- USD_CHF/trend: A R=-0.207199, B R=-0.210823, B-A=-0.003624; nA=192, nB=194.
- USD_CHF/mean_reversion: A R=-0.047011, B R=-0.057490, B-A=-0.010479; nA=90, nB=90.
- USD_CHF/swing_trend: A R=-0.197201, B R=-0.201072, B-A=-0.003871; nA=164, nB=168.
- USD_CHF/swing_mean_reversion: A R=-0.017690, B R=-0.032426, B-A=-0.014736; nA=64, nB=64.
- USD_CHF/swing_breakout: A R=-0.199021, B R=-0.188382, B-A=0.010639; nA=103, nB=104.

Secondary controlled ATR-research geometry A/B (not the default operational geometry):

- EUR_USD/scalp: A R=-0.277972, B R=-0.291220, B-A=-0.013248; nA=258, nB=274.
- EUR_USD/trend: A R=-0.277972, B R=-0.291220, B-A=-0.013248; nA=258, nB=274.
- EUR_USD/mean_reversion: A R=-0.354959, B R=-0.370416, B-A=-0.015457; nA=150, nB=152.
- EUR_USD/swing_trend: A R=-0.325086, B R=-0.315074, B-A=0.010012; nA=233, nB=248.
- EUR_USD/swing_mean_reversion: A R=-0.401000, B R=-0.411201, B-A=-0.010201; nA=128, nB=130.
- EUR_USD/swing_breakout: A R=-0.369238, B R=-0.366533, B-A=0.002705; nA=134, nB=138.
- GBP_USD/scalp: A R=-0.423002, B R=-0.417211, B-A=0.005792; nA=264, nB=275.
- GBP_USD/trend: A R=-0.423843, B R=-0.418039, B-A=0.005804; nA=265, nB=276.
- GBP_USD/mean_reversion: A R=-0.308367, B R=-0.332003, B-A=-0.023636; nA=148, nB=149.
- GBP_USD/swing_trend: A R=-0.420296, B R=-0.412298, B-A=0.007997; nA=224, nB=234.
- GBP_USD/swing_mean_reversion: A R=-0.290735, B R=-0.300701, B-A=-0.009966; nA=122, nB=124.
- GBP_USD/swing_breakout: A R=-0.496754, B R=-0.466932, B-A=0.029822; nA=133, nB=135.
- USD_JPY/scalp: A R=-0.265701, B R=-0.268453, B-A=-0.002752; nA=248, nB=254.
- USD_JPY/trend: A R=-0.265628, B R=-0.268371, B-A=-0.002743; nA=249, nB=255.
- USD_JPY/mean_reversion: A R=-0.150102, B R=-0.158605, B-A=-0.008503; nA=127, nB=128.
- USD_JPY/swing_trend: A R=-0.248223, B R=-0.251738, B-A=-0.003516; nA=218, nB=226.
- USD_JPY/swing_mean_reversion: A R=-0.232044, B R=-0.238887, B-A=-0.006842; nA=102, nB=103.
- USD_JPY/swing_breakout: A R=-0.204931, B R=-0.205700, B-A=-0.000769; nA=123, nB=126.
- AUD_USD/scalp: A R=-0.435229, B R=-0.421448, B-A=0.013782; nA=260, nB=263.
- AUD_USD/trend: A R=-0.435229, B R=-0.421448, B-A=0.013782; nA=260, nB=263.
- AUD_USD/mean_reversion: A R=-0.385440, B R=-0.369922, B-A=0.015518; nA=151, nB=152.
- AUD_USD/swing_trend: A R=-0.429400, B R=-0.419084, B-A=0.010316; nA=205, nB=214.
- AUD_USD/swing_mean_reversion: A R=-0.231549, B R=-0.238166, B-A=-0.006617; nA=111, nB=113.
- AUD_USD/swing_breakout: A R=-0.390201, B R=-0.375537, B-A=0.014664; nA=129, nB=131.
- USD_CAD/scalp: A R=-0.442051, B R=-0.443695, B-A=-0.001644; nA=268, nB=276.
- USD_CAD/trend: A R=-0.439329, B R=-0.441665, B-A=-0.002336; nA=267, nB=275.
- USD_CAD/mean_reversion: A R=-0.468362, B R=-0.479236, B-A=-0.010875; nA=156, nB=156.
- USD_CAD/swing_trend: A R=-0.481356, B R=-0.479570, B-A=0.001786; nA=241, nB=252.
- USD_CAD/swing_mean_reversion: A R=-0.353463, B R=-0.381653, B-A=-0.028189; nA=125, nB=125.
- USD_CAD/swing_breakout: A R=-0.431451, B R=-0.441731, B-A=-0.010280; nA=142, nB=143.
- USD_CHF/scalp: A R=-0.433647, B R=-0.436086, B-A=-0.002439; nA=257, nB=272.
- USD_CHF/trend: A R=-0.432988, B R=-0.433292, B-A=-0.000304; nA=259, nB=274.
- USD_CHF/mean_reversion: A R=-0.228705, B R=-0.238953, B-A=-0.010247; nA=137, nB=139.
- USD_CHF/swing_trend: A R=-0.497437, B R=-0.514607, B-A=-0.017169; nA=224, nB=227.
- USD_CHF/swing_mean_reversion: A R=-0.113977, B R=-0.152285, B-A=-0.038308; nA=103, nB=105.
- USD_CHF/swing_breakout: A R=-0.435071, B R=-0.450297, B-A=-0.015226; nA=121, nB=123.

Status: TIV2_OFFLINE_RESEARCH_PARTIALLY_VERIFIED. Production remains NO-GO. All results are hypothetical archived-data replay, never broker fills. The 29-day archive and short OOS windows do not establish statistical significance or live profitability.
