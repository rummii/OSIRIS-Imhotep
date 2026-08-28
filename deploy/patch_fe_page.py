"""Patch frontend/app/page.tsx to auto-save after generation and pass docId to SowReport."""
from pathlib import Path

p = Path(r"c:\Users\ahmad\OneDrive\Documents\OSIRIS Imhotep\frontend\app\page.tsx")
text = p.read_text(encoding="utf-8")

# 1. Update imports
old_imp = 'import { generateSow } from "@/lib/api";'
new_imp = 'import { generateSow, saveFromGeneration } from "@/lib/api";'
assert old_imp in text, "import not found"
text = text.replace(old_imp, new_imp)

# 2. Update Message union: track docId on assistant
old_msg = '  | { role: "assistant"; result: GenerateResponse }'
new_msg = '  | { role: "assistant"; result: GenerateResponse; docId: number | null }'
assert old_msg in text, "message type not found"
text = text.replace(old_msg, new_msg)

# 3. Update handleSubmit to call saveFromGeneration after generateSow
old_submit = '      const result = await generateSow(submission);\n      setMessages((prev) => [...prev, { role: "assistant", result }]);'
new_submit = '''      const result = await generateSow(submission);
      // Auto-save so the SOW appears in the Documents list and can be re-exported.
      let docId: number | null = null;
      try {
        const saved = await saveFromGeneration(result.sow);
        docId = saved.id;
      } catch (saveErr) {
        console.warn("Auto-save failed:", saveErr);
      }
      setMessages((prev) => [...prev, { role: "assistant", result, docId }]);'''
assert old_submit in text, f"submit pattern not found. Last 500:\n{text[text.find('generateSow(submission)'):text.find('generateSow(submission)')+500]}"
text = text.replace(old_submit, new_submit)

# 4. Update SowReport usage to pass docId (note: uses message.result, not result)
old_call = '''                <SowReport
                  sow={message.result.sow}
                  model={message.result.model}
                  grounding={message.result.grounding}
                  groundingSources={message.result.grounding_sources}
                />'''
new_call = '''                <SowReport
                  sow={message.result.sow}
                  model={message.result.model}
                  grounding={message.result.grounding}
                  groundingSources={message.result.grounding_sources}
                  docId={message.docId}
                />'''
assert old_call in text, f"SowReport call not found. Last 500:\n{text[text.find('SowReport'):text.find('SowReport')+500]}"
text = text.replace(old_call, new_call)

p.write_text(text, encoding="utf-8", newline="")
print("patched", p)
