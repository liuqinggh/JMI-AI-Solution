# 从保单 Markdown 应抽取的比对字段

用于与 OCR/视觉提取结果对照（字段名可按保单实际标题映射）：

| 逻辑字段 | 说明 |
|---------|------|
| `policy_number` | 保单号 |
| `policy_period_start` / `policy_period_end` | 保险期间起止（公历日期） |
| `insured_name_th` / `insured_name_en` | 被保险人姓名 |
| `insured_id` | 身份证号 |
| `phone` | 联系电话 |
| `registration` | 车牌（泰文+数字） |
| `registration_province` | 登记府/曼谷 |
| `make` / `model` / `year` | 品牌、型号、年款 |
| `chassis` | 车架号 VIN |
| `engine` | 发动机号 |
| `owner` | 所有权人（含租赁公司） |
| `possessor` | 占有人/使用人 |
| `own_damage_deductible_first_loss` | 车损首损免赔额（金额+币种） |

免赔额还可与 FCCS、定损单上的 deductible 文本交叉验证。
