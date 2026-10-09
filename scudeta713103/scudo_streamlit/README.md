# SCUDO MONETA

A clean Streamlit prototype for scam-awareness, payment-risk explanations, statement review, and practical safety guidance.

## Requirements

- Python 3.10 or newer
- Internet is only needed to install packages; the app itself does not call an external AI service.

## Run in PyCharm

1. Extract this ZIP.
2. Open the `scudo_streamlit` folder in PyCharm.
3. Select a Python 3.10+ interpreter.
4. Open the terminal at the project folder and run:

   ```bash
   python -m pip install -r requirements.txt
   python -m streamlit run streamlit_app.py
   ```

5. Open the local address printed in the terminal, usually `http://localhost:8501`.

## Sections

- **Protection Demo** — simulated payment risk checks with an explanation of each selected signal.
- **Statement Scanner** — attempts PDF table extraction, then a text fallback that supports wrapped transaction rows and month-first dates (for example, `Oct 09, 2026`) when the table layout is not detected. It prioritises currency-marked amounts to avoid confusing UTR or transaction IDs with amounts. Review extracted values against the original statement before relying on them. Scanned/image-only PDFs still need OCR, which is not included.
- **Analyst Dashboard** — illustrative synthetic data only.
- **Moneta Assistant** — local, rule-based English/Hindi guidance for common scam scenarios. It is not a generative AI model and does not contact banks or submit reports.
- **Safety & Privacy** — scope and limitations.

## Important limitations

- This is a demonstration prototype, not a validated fraud detector or a banking product.
- Risk scores are rule-based indicators, not probabilities of fraud.
- The statement parser supports common layouts but cannot guarantee correct extraction across every bank. It may misread debit, credit, or balance columns. Verify all extracted values against the original statement.
- The application does not connect to UPI, read SMS/calls, move money, block payments, verify account ownership, or file a cybercrime report.
- Use synthetic or redacted statements. Do not upload OTPs, PINs, passwords, account credentials, or unnecessary personal information.
