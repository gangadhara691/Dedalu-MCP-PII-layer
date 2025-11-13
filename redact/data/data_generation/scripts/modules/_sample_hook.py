# scripts/modules/sample_hook.py
def on_record(rec, base):
    # Example: normalize phone formatting or name casing (no-op here)
    pass

def on_render(rec, base, tex_path):
    # Example: post-process .tex (no-op)
    pass

def on_pdf(rec, base, pdf_path):
    # Example: log to external system (no-op)
    pass
