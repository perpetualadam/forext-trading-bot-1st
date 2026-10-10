# Archive cleanup request

Stage G.12.1 has not deleted this file.

- Path: `C:\Users\Brian\AppData\Local\Temp\forex-bot-g12-forensics\image_save.tar`
- Size: `111919104` bytes
- SHA-256: `ba6f8c3659a599bba1a1b322384ae462dc4d43e8de5a73b7f1001ecca606c948`
- Regular file: yes
- Parent directory retained: `C:\Users\Brian\AppData\Local\Temp\forex-bot-g12-forensics`
- Deletion reversible: no
- Evidence that remains: `data/research/adaptive_ensemble/g12/` and `data/research/adaptive_ensemble/g12_1/`
- Sensitive-data concern remaining: no credential value was stored in the scanned reports
- Proposed command:

```powershell
Remove-Item -LiteralPath "C:\Users\Brian\AppData\Local\Temp\forex-bot-g12-forensics\image_save.tar"
```

Cleanup approved: yes, by the operator's exact deletion script
Cleanup performed: yes
Deletion result: the identity, size, and SHA-256 checks passed, then only the archive was removed. The parent directory and `analyze_layers.py` remain.
