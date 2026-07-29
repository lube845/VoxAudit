<template>
  <div class="system-settings">
    <div class="page-header">
      <h2>系统设置</h2>
    </div>

    <el-tabs v-model="activeTab" class="settings-tabs">
      <!-- LLM配置 -->
      <el-tab-pane label="大模型配置" name="llm">
        <el-card class="config-card" shadow="hover">
          <template #header>
            <div class="card-title">
              <el-icon class="card-icon"><Connection /></el-icon>
              <span>大模型（LLM）配置</span>
            </div>
          </template>

          <el-form :model="llmForm" label-width="120px" label-position="left" class="settings-form">
            <el-form-item label="API密钥">
              <el-input
                v-model="llmForm.api_key"
                type="password"
                placeholder="请输入API密钥"
                show-password
                clearable
              >
                <template #append>
                  <el-tooltip content="留空则使用环境变量配置" placement="top">
                    <el-icon><InfoFilled /></el-icon>
                  </el-tooltip>
                </template>
              </el-input>
            </el-form-item>

            <el-form-item label="模型名称">
              <el-input v-model="llmForm.model" placeholder="例如：MiniMax-M2-7" clearable />
            </el-form-item>

            <el-form-item label="API地址">
              <el-input v-model="llmForm.api_endpoint" placeholder="例如：http://localhost:8080/v1/text/chatcompletion_v2" clearable />
            </el-form-item>

            <el-form-item label="Temperature">
              <div class="slider-input">
                <el-slider v-model="llmForm.temperature" :min="0" :max="2" :step="0.05" :show-tooltip="true" />
                <el-input-number v-model="llmForm.temperature" :min="0" :max="2" :precision="2" :step="0.1" size="small" />
              </div>
            </el-form-item>

            <el-form-item label="最大Token">
              <el-input-number v-model="llmForm.max_tokens" :min="100" :max="100000" :step="100" />
            </el-form-item>

            <el-form-item label="模型重试次数">
              <el-input-number v-model="llmForm.json_retry_count" :min="1" :max="10" />
            </el-form-item>
          </el-form>

          <div class="card-footer">
            <div class="footer-left">
              <span class="tip-text">* 测试通过后才能保存</span>
            </div>
            <div class="footer-right">
              <el-button @click="handleTestLlm" :loading="testingLlm" :type="llmTestResult === true ? 'success' : llmTestResult === false ? 'danger' : 'default'">
                <el-icon v-if="!testingLlm"><Bell /></el-icon>
                {{ testingLlm ? '测试中...' : llmTestResult === true ? '测试通过' : llmTestResult === false ? '测试失败' : '测试连通性' }}
              </el-button>
              <el-button type="primary" @click="handleSaveLlm" :loading="savingLlm" :disabled="!canSaveLlm">
                <el-icon v-if="!savingLlm"><Check /></el-icon>
                保存配置
              </el-button>
            </div>
          </div>
        </el-card>

        <!-- 当前生效配置 -->
        <el-card class="preview-card" shadow="never">
          <template #header>
            <div class="card-title">
              <el-icon class="card-icon"><Document /></el-icon>
              <span>当前生效配置（数据库）</span>
            </div>
          </template>
          <div class="config-preview">
            <div class="preview-item">
              <span class="preview-label">模型</span>
              <span class="preview-value">{{ currentLlmConfig.model || '-' }}</span>
            </div>
            <div class="preview-item">
              <span class="preview-label">API地址</span>
              <span class="preview-value">{{ currentLlmConfig.api_endpoint || '-' }}</span>
            </div>
            <div class="preview-item">
              <span class="preview-label">Temperature</span>
              <span class="preview-value">{{ currentLlmConfig.temperature }}</span>
            </div>
            <div class="preview-item">
              <span class="preview-label">最大Token</span>
              <span class="preview-value">{{ currentLlmConfig.max_tokens }}</span>
            </div>
            <div class="preview-item">
              <span class="preview-label">模型重试次数</span>
              <span class="preview-value">{{ currentLlmConfig.json_retry_count }} 次</span>
            </div>
            <div class="preview-item">
              <span class="preview-label">API密钥</span>
              <el-tag :type="currentLlmConfig.api_key ? 'success' : 'info'" size="small">
                {{ currentLlmConfig.api_key ? '已设置' : '未设置' }}
              </el-tag>
            </div>
          </div>
        </el-card>
      </el-tab-pane>

      <!-- ASR配置 -->
      <el-tab-pane label="ASR配置" name="asr">
        <el-card class="config-card" shadow="hover">
          <template #header>
            <div class="card-title">
              <el-icon class="card-icon"><Microphone /></el-icon>
              <span>语音识别（ASR）配置</span>
            </div>
          </template>

          <el-form :model="asrForm" label-width="120px" label-position="left" class="settings-form">
            <el-form-item label="API地址">
              <el-input v-model="asrForm.api_url" placeholder="例如：http://localhost:8080" clearable />
            </el-form-item>

            <el-form-item label="API密钥">
              <el-input
                v-model="asrForm.api_key"
                type="password"
                placeholder="请输入API密钥"
                show-password
                clearable
              >
                <template #append>
                  <el-tooltip content="留空则使用环境变量配置" placement="top">
                    <el-icon><InfoFilled /></el-icon>
                  </el-tooltip>
                </template>
              </el-input>
            </el-form-item>
          </el-form>

          <div class="card-footer">
            <div class="footer-left">
              <span class="tip-text">* 测试通过后才能保存</span>
            </div>
            <div class="footer-right">
              <el-button @click="handleTestAsr" :loading="testingAsr" :type="asrTestResult === true ? 'success' : asrTestResult === false ? 'danger' : 'default'">
                <el-icon v-if="!testingAsr"><Bell /></el-icon>
                {{ testingAsr ? '测试中...' : asrTestResult === true ? '测试通过' : asrTestResult === false ? '测试失败' : '测试连通性' }}
              </el-button>
              <el-button type="primary" @click="handleSaveAsr" :loading="savingAsr" :disabled="!canSaveAsr">
                <el-icon v-if="!savingAsr"><Check /></el-icon>
                保存配置
              </el-button>
            </div>
          </div>
        </el-card>

        <!-- ASR当前配置 -->
        <el-card class="preview-card" shadow="never">
          <template #header>
            <div class="card-title">
              <el-icon class="card-icon"><Document /></el-icon>
              <span>当前生效配置（数据库）</span>
            </div>
          </template>
          <div class="config-preview">
            <div class="preview-item">
              <span class="preview-label">API地址</span>
              <span class="preview-value">{{ currentAsrConfig.api_url || '-' }}</span>
            </div>
            <div class="preview-item">
              <span class="preview-label">API密钥</span>
              <el-tag :type="currentAsrConfig.api_key ? 'success' : 'info'" size="small">
                {{ currentAsrConfig.api_key ? '已设置' : '未设置' }}
              </el-tag>
            </div>
          </div>
        </el-card>
      </el-tab-pane>

      <!-- Prompt配置 -->
      <el-tab-pane label="Prompt配置" name="prompt">
        <el-card class="config-card" shadow="hover">
          <template #header>
            <div class="card-header">
              <div class="card-title">
                <el-icon class="card-icon"><ChatDotRound /></el-icon>
                <span>大模型Prompt配置</span>
              </div>
              <div class="header-actions">
                <el-button @click="handleResetPrompts" :loading="resettingPrompts" size="small">
                  <el-icon><Refresh /></el-icon>
                  重置为默认
                </el-button>
                <el-button type="primary" @click="handleSavePrompts" :loading="savingPrompts" :disabled="!hasPromptChanges">
                  <el-icon v-if="!savingPrompts"><Check /></el-icon>
                  保存配置
                </el-button>
              </div>
            </div>
          </template>

          <el-form :model="promptForm" label-width="140px" label-position="left" class="prompt-form">
            <el-form-item label="客服/客户区分">
              <el-input
                v-model="promptForm.speaker_detection"
                type="textarea"
                :rows="6"
                placeholder="用于区分录音中说话人是坐席还是客户的Prompt模板"
              />
              <div class="form-tip">模板变量：{speaker_count}（说话人数量）、{dialogue_text}（对话内容）</div>
            </el-form-item>

            <el-form-item label="规则细化">
              <el-input
                v-model="promptForm.rule_refine"
                type="textarea"
                :rows="6"
                placeholder="用于将粗略规则细化为结构化规则的Prompt模板"
              />
              <div class="form-tip">模板变量：{original_description}（原始规则描述）</div>
            </el-form-item>

            <el-form-item label="加分规则判定">
              <el-input
                v-model="promptForm.bonus_judgment"
                type="textarea"
                :rows="10"
                placeholder="用于判断录音是否命中加分规则的Prompt模板"
              />
              <div class="form-tip">模板变量：{transcript}（转写文本）、{segments}（对话片段）、{rules_json}（规则JSON）</div>
            </el-form-item>

            <el-form-item label="减分规则判定">
              <el-input
                v-model="promptForm.deduction_judgment"
                type="textarea"
                :rows="10"
                placeholder="用于判断录音是否命中减分规则的Prompt模板"
              />
              <div class="form-tip">模板变量：{transcript}（转写文本）、{segments}（对话片段）、{rules_json}（规则JSON）</div>
            </el-form-item>
          </el-form>
        </el-card>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Connection, Setting, Document, Check, InfoFilled, Microphone, Bell, ChatDotRound, Refresh } from '@element-plus/icons-vue'
import api from '@/api'

const activeTab = ref('llm')
const loading = ref(false)
const savingLlm = ref(false)
const savingAsr = ref(false)
const savingPrompts = ref(false)
const resettingPrompts = ref(false)
const testingLlm = ref(false)
const testingAsr = ref(false)
const llmTestResult = ref(null)
const asrTestResult = ref(null)
const llmTestMessage = ref('')
const asrTestMessage = ref('')

const llmForm = ref({
  api_key: '',
  model: '',
  api_endpoint: '',
  temperature: 0.1,
  max_tokens: 2000,
  json_retry_count: 3,
})

const asrForm = ref({
  api_url: '',
  api_key: '',
})

// 默认 Prompt 模板
const DEFAULT_PROMPTS = {
  speaker_detection: `你是一名资深的催收对话质检专员，任务是根据通话转写内容，判断每个speaker对应的角色：坐席（催收人员）还是客户（欠款人/家属/第三方）。

【背景】
这是一段催收场景的外呼录音转写，已通过声纹识别切分出 {len(speakers)} 个speaker。转写中可能包含"开始录音""通话结束"等系统提示音被误转写为文本的情况，判断时请忽略这类内容，不要作为角色依据。

【判断依据，按优先级参考】
1. 身份表述：主动报出机构名称、工号、"是XX本人吗"等确认身份用语的，通常是坐席；应答"我是"、反问"你是哪里的"的，通常是客户
2. 业务话术：提及欠款金额、逾期天数、还款期限、法律后果、征信影响、协商方案等催缴/引导性内容的，通常是坐席
3. 应答模式：说明拖欠原因、讨价还价、请求宽限、表达情绪（不满/为难/推诿）的，通常是客户
4. 话轮特征：全程提问多、主导话题走向的更可能是坐席；被动回应、简短应答（"嗯""知道了""再说吧"）多的更可能是客户
5. 结束语：主动说"祝您生活愉快""再见，我们会保留记录"等标准结束语的通常是坐席

【需要注意的特殊情况】
- 如果某个说话人的发言内容全部是环境音、提示音或无实际语义的碎片，请在reasoning中说明，并将该说话人标记为"unknown"
- 如果对话涉及转接（如"我帮您转接家属"）或非本人接听（如家属代接），请在reasoning中特别说明这一情况
- 如果内容过短或信息不足以支撑判断，请标记为"unknown"，不要强行猜测
- 一通对话中坐席角色是唯一的，如果超过2个speaker，请判断是否存在插入/串音的干扰speaker

【转写内容】
{dialogue_text}

【输出要求】
只返回如下JSON格式，不要输出任何额外说明文字：
{{
  "speaker_roles": {{
    "speaker_0": "agent" 或 "customer" 或 "unknown",
    ...
  }},
  "confidence": "high" 或 "medium" 或 "low",
  "reasoning": "简要说明判断依据，30-50字以内，若有特殊情况（转接/代接/信息不足）请注明"
}}`,

  rule_refine: `你是一名专业的金融催收录音质检专家，负责将业务人员提供的粗略质检规则描述，细化为结构清晰、可直接用于大模型评分的标准化规则。

## 原始规则描述
{request.description}

## 细化任务
请围绕原始规则描述，从以下维度进行细化。注意：只做"细化"和"结构化"，不要引入原描述中没有的判断逻辑，不要扩大或缩小规则的判断范围。

1. **基础描述**：用一句话概括命中判定的核心标准，不展开细节
2. **触发条件**：详细说明具体的识别逻辑，包括：
   - 需要出现的具体话术、行为或情境特征（条件要具体到可操作，避免"态度不好""不专业"这类模糊表述）
   - 是否需要结合上下文多轮内容才能判断，还是单句出现即可判定（若原描述未说明，基于业务常识给出合理默认，并标注"推断"）
3. **正面示例**：3-5条具体的话术片段或场景，覆盖不同表达方式（直接表述、委婉表述、口语化表述）
4. **负面示例**：2-3条相似但不应判定命中的场景，帮助模型避免误判

## 约束
- 严格保持原始规则的意图，不新增、不删减规则实质内容
- 每个字段内容简洁，避免空话套话
- 该规则只要出现一次即判定命中，无需考虑频次或比例
- 若信息不足以支撑某个判断维度，基于业务常识合理默认，并在对应位置用"（推断）"标注

## 输出格式
只输出如下格式的文字，标记符号必须严格使用【】，各项之间用换行分隔，不要输出任何额外说明文字、前缀或Markdown代码块标记：

【基础描述】命中判定标准的一句话概括，50字以内
【触发条件】具体识别逻辑的完整说明，150字以内
【正面示例】1.示例话术或场景1；2.示例话术或场景2；3.示例话术或场景3
【负面示例】1.易混淆但不命中的场景1；2.易混淆但不命中的场景2`,

  bonus_judgment: `你是一名专业的金融催收录音质检专家，负责根据标准化加分规则，逐条判断坐席在本次通话中的表现是否命中。

## 录音转写文本
{transcript}

## 对话片段详情
{json.dumps(segments, ensure_ascii=False, indent=2)}

## 加分规则
{rules_json}

## 评分原则

1. **逐条独立判断**：每条规则单独判断，不要因为坐席整体表现好/差而互相影响评分

2. **严格依据规则字段判断**：
   - 参考"基础描述"确定命中的核心标准
   - 参考"触发条件"确定具体的识别逻辑，包括是否需要结合上下文多轮内容判断（若触发条件中说明需要多轮上下文，请勿仅凭孤立单句下结论）
   - 参考"正面示例"理解命中话术的典型表达方式（包括委婉、口语化变体，不要求与示例逐字匹配）
   - 参考"负面示例"排除易混淆但不应命中的情况，如果坐席表现与负面示例描述的场景相似，应判定为not_matched

3. **判断对象**：除非规则的触发条件中另有说明，默认只判断坐席的发言表现，客户发言仅作为理解对话语境的参考，不作为命中依据

4. **一票命中**：所有加分规则均为一次性判定，只要出现一次符合触发条件的表现即判定为matched，无需考虑出现次数或比例

5. **证据来源约束（重要）**：
   - \`matched_text\`必须是转写文本或对话片段中**真实出现的原文片段**，禁止改写、总结或编造
   - 如果需结合上下文才能判断，\`matched_text\`可以填入多个片段并用"..."分隔，但每个片段都必须真实存在
   - 如果找不到明确的原文证据支撑matched，不能标记为matched，即使你认为坐席"整体做到了"

6. **宁缺勿滥**：证据不充分、表述模糊、无法确定是否达到规则要求时，一律判定为"not_matched"，不要主观推测坐席意图

## 需要触发warnings的情况
以下情况请填入warnings数组，用简短文字描述，不影响加分规则的matched/not_matched判断：
- 转写内容存在明显缺失、乱码或大段无法识别，可能影响本次评分准确性
- 角色疑似标注错误，如坐席话术出现在客户角色下
- 出现规则未覆盖但明显违规的高风险行为（如泄露他人隐私、辱骂、暴力威胁等），仅作为风险提示，不影响本次加分规则评分
如无上述情况，返回空数组，不要为了填充而输出无意义内容。

## 输出格式要求（JSON）
{{
    "items": [
        {{
            "code": "规则代码",
            "status": "matched" 或 "not_matched",
            "matched_text": "命中的原文证据，多处用...分隔；未命中则为空字符串",
            "reason": "评分理由，需说明依据触发条件的哪个部分得出结论，30-60字"
        }}
    ],
    "warnings": ["风险预警描述，如有则填入，否则为空数组"]
}}

请严格按照上述JSON格式输出，不要包含Markdown代码块标记或其他任何额外文字。`,

  deduction_judgment: `你是一名专业的金融催收录音质检专家，负责根据标准化减分规则，逐条判断坐席在本次通话中的表现是否存在违规行为。

## 录音转写文本
{transcript}

## 对话片段详情
{json.dumps(segments, ensure_ascii=False, indent=2)}

## 减分规则
{rules_json}

## 评分原则

1. **逐条独立判断**：每条规则单独判断，不要因为坐席整体表现好/差而互相影响判断

2. **严格依据规则字段判断**：
   - 参考"基础描述"确定违规的核心标准
   - 参考"触发条件"确定具体的识别逻辑，包括是否需要结合上下文多轮内容判断（若触发条件中说明需要多轮上下文，请勿仅凭孤立单句下结论）
   - 参考"正面示例"理解违规话术的典型表达方式（包括委婉、口语化变体，不要求与示例逐字匹配）
   - 参考"负面示例"排除易混淆但不构成违规的情况，如果坐席表现与负面示例描述的场景相似，应判定为not_matched

3. **判断对象**：除非规则的触发条件中另有说明，默认只判断坐席的发言表现，客户发言仅作为理解对话语境的参考，不作为违规依据

4. **一票命中**：所有减分规则均为一次性判定，只要出现一次符合触发条件的违规表现即判定为matched，无需考虑出现次数或比例

5. **证据从严原则（重要，扣分类规则误判成本高于加分规则）**：
   - \`matched_text\`必须是转写文本或对话片段中**真实出现的原文片段**，禁止改写、总结或编造
   - 如果坐席的表述存在多种合理解读（如引用政策条文说明 vs 威胁施压），且转写文本本身无法排除善意/合规的解读，一律判定为"not_matched"，不做有罪推定
   - 语气、态度类的模糊感受（如"感觉不耐烦"）不能作为判定依据，必须有具体话术或行为作为支撑
   - 如果只是客户单方面的指责或情绪化转述（如客户说"你态度很差"），而转写文本中坐席实际发言未见明确违规话术，不能仅凭客户的说法判定matched

6. **宁缺勿滥**：证据不充分、表述模糊、无法确定是否构成违规时，一律判定为"not_matched"，不要主观推测坐席意图或"可能存在"违规

## 需要触发warnings的情况（而非用于减分判断）
以下情况请填入warnings数组，用简短文字描述，不影响减分规则的matched/not_matched判断：
- 转写内容存在明显缺失、乱码或大段无法识别，可能影响本次评分准确性
- 角色疑似标注错误，如坐席话术出现在客户角色下
- 出现规则未覆盖但明显违规的高风险行为（如泄露他人隐私、辱骂、暴力威胁、暗示非法催收手段等），仅作为风险提示，不影响本次减分规则评分，但请如实描述具体内容以便人工复核
如无上述情况，返回空数组，不要为了填充而输出无意义内容。

## 输出格式要求（JSON）
{{
    "items": [
        {{
            "code": "规则代码",
            "status": "matched" 或 "not_matched",
            "matched_text": "违规的原文证据，多处用...分隔；未违规则为空字符串",
            "reason": "扣分理由，需说明依据触发条件的哪个部分得出结论，30-60字"
        }}
    ],
    "warnings": ["风险预警描述，如有则填入，否则为空数组"]
}}

请严格按照上述JSON格式输出，不要包含Markdown代码块标记或其他任何额外文字。`,
}

const promptForm = ref({ ...DEFAULT_PROMPTS })

const promptFormDefault = ref({ ...DEFAULT_PROMPTS })

const currentLlmConfig = ref({})
const currentAsrConfig = ref({})

const hasLlmChanges = computed(() => {
  return llmForm.value.model !== currentLlmConfig.value.model ||
    llmForm.value.api_endpoint !== currentLlmConfig.value.api_endpoint ||
    llmForm.value.temperature !== currentLlmConfig.value.temperature ||
    llmForm.value.max_tokens !== currentLlmConfig.value.max_tokens ||
    llmForm.value.json_retry_count !== currentLlmConfig.value.json_retry_count ||
    llmForm.value.api_key !== ''
})

const hasAsrChanges = computed(() => {
  return asrForm.value.api_url !== currentAsrConfig.value.api_url ||
    asrForm.value.api_key !== ''
})

const hasPromptChanges = computed(() => {
  return promptForm.value.speaker_detection !== promptFormDefault.value.speaker_detection ||
    promptForm.value.rule_refine !== promptFormDefault.value.rule_refine ||
    promptForm.value.bonus_judgment !== promptFormDefault.value.bonus_judgment ||
    promptForm.value.deduction_judgment !== promptFormDefault.value.deduction_judgment
})

const canSaveLlm = computed(() => {
  return hasLlmChanges.value && llmTestResult.value === true
})

const canSaveAsr = computed(() => {
  return hasAsrChanges.value && asrTestResult.value === true
})

async function loadConfig() {
  loading.value = true
  try {
    const [configData, llmData, promptsData] = await Promise.all([
      api.systemSettings.getConfig(),
      api.systemSettings.getLlmConfig(),
      api.systemSettings.getPrompts(),
    ])

    llmForm.value = {
      api_key: '',
      model: configData.llm.model || '',
      api_endpoint: configData.llm.api_endpoint || '',
      temperature: configData.llm.temperature || 0.1,
      max_tokens: configData.llm.max_tokens || 2000,
      json_retry_count: configData.llm.json_retry_count || 3,
    }

    asrForm.value = {
      api_url: configData.asr.api_url || '',
      api_key: '',
    }

    promptForm.value = {
      speaker_detection: promptsData.speaker_detection || DEFAULT_PROMPTS.speaker_detection,
      rule_refine: promptsData.rule_refine || DEFAULT_PROMPTS.rule_refine,
      bonus_judgment: promptsData.bonus_judgment || DEFAULT_PROMPTS.bonus_judgment,
      deduction_judgment: promptsData.deduction_judgment || DEFAULT_PROMPTS.deduction_judgment,
    }
    promptFormDefault.value = { ...promptForm.value }

    currentLlmConfig.value = { ...llmData }
    currentAsrConfig.value = { ...configData.asr }

    llmTestResult.value = null
    asrTestResult.value = null
    llmTestMessage.value = ''
    asrTestMessage.value = ''
  } catch (e) {
    console.error('加载配置失败', e)
    ElMessage.error('加载配置失败')
  } finally {
    loading.value = false
  }
}

async function handleTestLlm() {
  testingLlm.value = true
  llmTestResult.value = null
  llmTestMessage.value = ''
  try {
    const result = await api.systemSettings.testLlmConfig({
      api_key: llmForm.value.api_key || null,
      model: llmForm.value.model || null,
      api_endpoint: llmForm.value.api_endpoint || null,
      temperature: llmForm.value.temperature,
      max_tokens: llmForm.value.max_tokens,
      json_retry_count: llmForm.value.json_retry_count,
    })
    llmTestResult.value = result.success
    llmTestMessage.value = result.message
    if (!result.success) {
      ElMessage.error(result.message)
    }
  } catch (e) {
    llmTestResult.value = false
    llmTestMessage.value = '测试失败'
    console.error('测试LLM配置失败', e)
  } finally {
    testingLlm.value = false
  }
}

async function handleTestAsr() {
  testingAsr.value = true
  asrTestResult.value = null
  asrTestMessage.value = ''
  try {
    const result = await api.systemSettings.testAsrConfig({
      api_url: asrForm.value.api_url || null,
      api_key: asrForm.value.api_key || null,
    })
    asrTestResult.value = result.success
    asrTestMessage.value = result.message
    if (!result.success) {
      ElMessage.error(result.message)
    }
  } catch (e) {
    asrTestResult.value = false
    asrTestMessage.value = '测试失败'
    console.error('测试ASR配置失败', e)
  } finally {
    testingAsr.value = false
  }
}

async function handleSaveLlm() {
  savingLlm.value = true
  try {
    await api.systemSettings.updateLlmConfig({
      api_key: llmForm.value.api_key || null,
      model: llmForm.value.model || null,
      api_endpoint: llmForm.value.api_endpoint || null,
      temperature: llmForm.value.temperature,
      max_tokens: llmForm.value.max_tokens,
      json_retry_count: llmForm.value.json_retry_count,
    })
    ElMessage.success('LLM配置保存成功')
    await loadConfig()
  } catch (e) {
    console.error('保存LLM配置失败', e)
    ElMessage.error('保存LLM配置失败')
  } finally {
    savingLlm.value = false
  }
}

async function handleSaveAsr() {
  savingAsr.value = true
  try {
    await api.systemSettings.updateAsrConfig({
      api_url: asrForm.value.api_url || null,
      api_key: asrForm.value.api_key || null,
    })
    ElMessage.success('ASR配置保存成功')
    await loadConfig()
  } catch (e) {
    console.error('保存ASR配置失败', e)
    ElMessage.error('保存ASR配置失败')
  } finally {
    savingAsr.value = false
  }
}

async function handleSavePrompts() {
  savingPrompts.value = true
  try {
    await api.systemSettings.updatePrompts({
      speaker_detection: promptForm.value.speaker_detection,
      rule_refine: promptForm.value.rule_refine,
      bonus_judgment: promptForm.value.bonus_judgment,
      deduction_judgment: promptForm.value.deduction_judgment,
    })
    ElMessage.success('Prompt配置保存成功')
    await loadConfig()
  } catch (e) {
    console.error('保存Prompt配置失败', e)
    const detail = e?.response?.data?.detail || e?.message || '保存失败'
    ElMessage.error(detail)
  } finally {
    savingPrompts.value = false
  }
}

async function handleResetPrompts() {
  resettingPrompts.value = true
  try {
    await api.systemSettings.resetPrompts()
    ElMessage.success('已重置为默认Prompt模板')
    await loadConfig()
  } catch (e) {
    console.error('重置Prompt失败', e)
    ElMessage.error('重置Prompt失败')
  } finally {
    resettingPrompts.value = false
  }
}

onMounted(() => {
  loadConfig()
})
</script>

<style scoped>
.system-settings {
  padding: 0;
}

.page-header {
  margin-bottom: 20px;
}

.page-header h2 {
  margin: 0;
  font-size: 24px;
  font-weight: 600;
  color: #303133;
}

.settings-tabs {
  background: #fff;
  padding: 20px;
  border-radius: 4px;
}

.config-card {
  margin-bottom: 16px;
}

.config-card :deep(.el-card__header) {
  padding: 16px 20px;
  background: #f8f9fb;
  border-bottom: 1px solid #ebeef5;
}

.config-card :deep(.el-card__body) {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  font-size: 15px;
  color: #303133;
}

.header-actions {
  display: flex;
  gap: 8px;
}

.card-icon {
  font-size: 18px;
  color: #409eff;
}

.settings-form {
  max-width: 700px;
}

.prompt-form {
  max-width: 900px;
}

.prompt-form :deep(.el-textarea) {
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
  font-size: 13px;
}

.card-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 24px;
  padding-top: 16px;
  border-top: 1px solid #ebeef5;
  flex-wrap: wrap;
  gap: 12px;
}

.footer-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.footer-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.test-message {
  font-size: 13px;
}

.test-message.success {
  color: #67c23a;
}

.test-message.error {
  color: #f56c6c;
}

.tip-text {
  font-size: 12px;
  color: #909399;
}

.form-tip {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
  line-height: 1.4;
}

.preview-card {
  background: #fafafa;
  border: 1px dashed #dcdfe6;
}

.preview-card :deep(.el-card__header) {
  padding: 12px 20px;
  background: transparent;
  border-bottom: 1px dashed #dcdfe6;
}

.preview-card :deep(.el-card__body) {
  padding: 16px 20px;
}

.config-preview {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 16px;
}

.preview-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.preview-label {
  font-size: 12px;
  color: #909399;
}

.preview-value {
  font-size: 14px;
  color: #303133;
  font-weight: 500;
  word-break: break-all;
}

.slider-input {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
}

.slider-input :deep(.el-slider) {
  flex: 1;
}

.slider-input :deep(.el-input-number) {
  width: 100px;
}

:deep(.el-form-item__label) {
  font-weight: 500;
}
</style>
