# Document AI Processor 预设（axinan-prod）

项目 `660077994974`，location `us`。脚本通过 `--preset <name>` 使用下表预设。

| 预设名（--preset） | Processor 类型 | Processor ID |
|-------------------|---------------|--------------|
| ktp | KTP（印尼身份证） | 10dee3ae32570cdf |
| death_certificate | Death Certificate | b55397f6cb350861 |
| identifier_classifier | Identifier Classifier | 148acbbd72e20e4b |
| medical_bill | Medical Bill | 229170d253e069b6 |
| police_report | Police Report | ca0026f3dc9b92f7 |
| traveloka_delay | Traveloka Delay Confirmation | d2a8bd41f571631c |
| traveloka_classifier | Traveloka Documents Classifier | 74a98509ba0fac75 |

示例：

```bash
python scripts/documentAI_sample.py -f /path/to/doc.pdf --preset death_certificate
python scripts/documentAI_sample.py -f /path/to/medical.png --preset medical_bill --output entities
```

KTP 也可继续用 `--ktp`，等价于 `--preset ktp`。
