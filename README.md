# Cyber Agent — إيجنت يومي لمحتوى الأمن السيبراني (إنستغرام)

إيجنت يعمل تلقائياً كل يوم عبر **Railway**:
1. يبحث عن أهم خبر/ثغرة سيبرانية (باستخدام Anthropic API + أداة البحث بالويب).
2. يصنّفه ويقيّم أولويته.
3. يكتب محتوى عربي احترافي كامل (عنوان، شرح، تأثير، إجراءات، نصيحة، CTA، هاشتاقات).
4. يصمم 3 صور بهوية بصرية سيبرانية (Modern Minimal، بدون أشخاص).
5. اختيارياً: يرفع الصورة إلى GitHub وينشر المنشور مباشرة على Instagram عبر Meta Graph API.

---

## 0) قبل البدء — الوضع الافتراضي آمن
الإيجنت يعمل افتراضياً في **وضع المراجعة (Dry Run)**: يولّد كل شيء ويحفظه في مجلد
`posts/التاريخ/` بدون أي نشر فعلي. لا يتحول للنشر التلقائي إلا بعد أن تضبط
`AUTO_PUBLISH=true` بنفسك — بعد أن تتأكد من جودة المحتوى والتصاميم لعدة أيام.

---

## 1) رفع المشروع إلى GitHub

```bash
cd cyber-agent
git init
git add .
git commit -m "Initial commit: cyber security daily agent"
git branch -M main
git remote add origin https://github.com/USERNAME/cyber-agent.git
git push -u origin main
```

> أنشئ المستودع أولاً من github.com (يُفضّل **Private** لأنه سيحتوي لاحقاً على صور
> منشورة، وربما بيانات حسّاسة إن أضفتها بالخطأ — احرص أن يبقى `.env` خارج git كما
> هو محدد في `.gitignore`).

---

## 2) ربط المشروع بـ Railway

1. ادخل إلى https://railway.app → **New Project** → **Deploy from GitHub repo**.
2. اختر مستودع `cyber-agent`.
3. Railway سيقرأ `railway.toml` تلقائياً (Nixpacks + جدولة Cron).
4. في تبويب **Variables**، أضف كل المتغيرات الموجودة في `.env.example` بقيمها
   الحقيقية (لا ترفع ملف `.env` نفسه إلى GitHub أبداً).
5. عدّل `cronSchedule` داخل `railway.toml` إذا أردت وقتاً مختلفاً (الصيغة UTC).
   المثال الحالي `0 2 * * *` = الساعة 6:00 صباحاً بتوقيت الإمارات (UTC+4).

بعد الحفظ، سيقوم Railway بتشغيل `python agent_runner.py` تلقائياً حسب الجدول —
حتى لو جهازك مغلق تماماً.

---

## 3) تجهيز مفتاح Anthropic API

من https://console.anthropic.com → API Keys → أنشئ مفتاحاً وضعه في متغير
`ANTHROPIC_API_KEY` على Railway.

---

## 4) تجهيز GitHub Token (لاستضافة الصور فقط)

هذا مطلوب فقط عند تفعيل `AUTO_PUBLISH=true`، لأن Instagram Graph API يحتاج رابط
صورة عام (`image_url`) وقت النشر — نستخدم GitHub نفسه كمستودع صور بدل خادم منفصل.

1. GitHub → Settings → Developer settings → **Personal access tokens (Fine-grained)**.
2. صلاحيات: `Contents: Read and write` على مستودع `cyber-agent` فقط.
3. ضع القيمة في `GITHUB_TOKEN`، واسم المستودع في `GITHUB_REPO` (مثل `username/cyber-agent`).

---

## 5) تجهيز حساب Instagram للنشر (اختياري — فقط لو تريد نشراً تلقائياً كاملاً)

النشر التلقائي على Instagram يتطلب حساب **Instagram Professional (Business/Creator)**
مرتبطاً بصفحة Facebook، وتطبيق Meta. الخطوات:

1. تأكد أن حساب Instagram Professional مرتبط بصفحة Facebook (من إعدادات الحساب).
2. اذهب إلى https://developers.facebook.com → **My Apps** → أنشئ تطبيقاً جديداً
   (نوع Business).
3. أضف منتج **Instagram Graph API** للتطبيق.
4. من Graph API Explorer، ولّد Access Token بصلاحيات:
   `instagram_basic`, `instagram_content_publish`, `pages_show_list`, `pages_read_engagement`.
5. حوّل التوكن إلى **Long-Lived Token** (صالح ~60 يوماً، ويُجدَّد قبل انتهائه):
   ```
   GET https://graph.facebook.com/v20.0/oauth/access_token
     ?grant_type=fb_exchange_token
     &client_id={app-id}
     &client_secret={app-secret}
     &fb_exchange_token={short-lived-token}
   ```
6. استخرج معرّف حساب Instagram Business مرة واحدة:
   ```
   GET https://graph.facebook.com/v20.0/{page-id}?fields=instagram_business_account&access_token={token}
   ```
   الرقم الناتج هو `IG_BUSINESS_ACCOUNT_ID`.
7. ضع التوكن في `IG_ACCESS_TOKEN` والمعرّف في `IG_BUSINESS_ACCOUNT_ID` على Railway.

> ملاحظة: التوكنات طويلة الأمد تنتهي كل ~60 يوماً وتحتاج تجديداً يدوياً أو عبر
> Meta App Review لصلاحيات دائمة أوسع (خارج نطاق هذا الإيجنت البسيط).

---

---

## 5.5) (اختياري) تفعيل خلفيات فنية أعلى جودة عبر OpenAI Images API

هذا اختياري بالكامل. بدونه، الإيجنت يعمل ويصمم كل شيء محلياً بـ Pillow مجاناً
كما كان. بتفعيله، يُستخدم OpenAI فقط لتوليد **خلفية فنية بدون أي نص**، ثم
يُضاف النص العربي فوقها بنفس محرك الخطوط الموثوق (لأن نماذج توليد الصور ترتكب
أخطاء إملائية عند كتابة نصوص عربية مباشرة).

⚠️ **مهم جداً:** اشتراك **ChatGPT Plus لا يفيد هنا إطلاقاً** — هو منتج منفصل
تماماً عن OpenAI API من ناحية الفوترة والوصول. تحتاج حساب API مستقل:

1. اذهب إلى **platform.openai.com** (وليس chatgpt.com) وسجّل الدخول/أنشئ حساباً.
2. من القائمة الجانبية: **Billing** → أضف بطاقة ائتمان (أول 5$ عادة مجانية
   لحساب جديد).
3. من القائمة الجانبية: **API keys** → **Create new secret key** → انسخه فوراً
   (يظهر مرة واحدة فقط، يبدأ بـ `sk-...`).
4. في Railway → Variables، أضف:
   ```
   OPENAI_API_KEY=sk-...
   OPENAI_IMAGE_QUALITY=medium
   ```
5. (مستحسن) اضبط سقف إنفاق شهري من **Billing → Limits** لتفادي أي استهلاك غير متوقع.

**التكلفة التقريبية:** صورة واحدة يومياً بجودة `medium` ≈ 0.04-0.07$، أي أقل من
3$ شهرياً تقريباً. إن فشل الاستدعاء لأي سبب (رصيد منتهٍ، خطأ شبكة)، يسجّل
الإيجنت تحذيراً في السجلات ويكمل تلقائياً بالتصميم المحلي المجاني بدل التوقف.

---

## 6) التشغيل محلياً للاختبار (اختياري)

```bash
python -m venv venv
source venv/bin/activate       # أو venv\Scripts\activate على ويندوز
pip install -r requirements.txt
cp .env.example .env            # ثم عدّل القيم داخله
python agent_runner.py
```

راجع المخرجات داخل `posts/<التاريخ>/` — ملف `content.json` والتصاميم الثلاثة.

---

## 7) بنية المشروع

```
cyber-agent/
├── agent_runner.py         # نقطة التشغيل الرئيسية
├── content_generator.py    # البحث + التصنيف + كتابة المحتوى (Anthropic API)
├── image_generator.py      # توليد 3 تصاميم PNG بالهوية البصرية (Pillow)
├── openai_image_generator.py  # خلفية فنية اختيارية عبر OpenAI Images API
├── github_uploader.py      # رفع الصورة لـ GitHub للحصول على رابط عام
├── instagram_publisher.py  # النشر عبر Meta Graph API
├── fonts/                  # خطوط عربية (Noto Sans Arabic)
├── posts/                  # المخرجات اليومية (تُنشأ تلقائياً)
├── railway.toml            # إعداد الجدولة اليومية على Railway
├── requirements.txt
└── .env.example
```

---

## حدود ونقاط يجب الانتباه لها
- **لا صور فوتوغرافية لأشخاص**: التصاميم رمزية/تجريدية بالكامل (شبكات، دروع،
  أقفال) تماشياً مع حدود توليد الصور — لا يتم تصوير أشخاص حقيقيين أو تمثيلهم.
- **مراجعة بشرية موصى بها دائماً**: حتى مع `AUTO_PUBLISH=true`، يُفضّل مراجعة أول
  عدة أيام من المخرجات في `posts/` قبل الوثوق الكامل بالنشر الآلي.
- **الثغرات الأمنية**: المحتوى يشرح التأثير والتخفيف فقط، ولا يذكر تفاصيل استغلال.
- **حقوق الملكية**: كل النصوص تُعاد صياغتها؛ لا يُنسخ أي نص حرفي من المصادر.
- **تكلفة API**: كل تشغيل يومي يستهلك طلب Anthropic API واحداً (مع بحث ويب) —
  تحقق من حدود/تكلفة حسابك على console.anthropic.com.
