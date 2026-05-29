# Global Language Linguistic Rules & Instructions for Translation, QA, Transcription and Subtitling Services

This document serves as the master linguistic reference for the ErrorSweep AI-powered translation and QA platform. It dictates the structural, typographical, and cultural rules required to achieve native-level localization quality across global languages.

**Legend:**
*   ⚠️ Rule differs significantly from English conventions.
*   🔍 Critical rule for Quality Assurance (QA) checks.
*   🌐 Cultural sensitivity or localization note.

---

## Hindi
### Implementation Status: Implemented in ErrorSweep

### 1. GRAMMAR RULES
*   ⚠️ **Sentence structure:** Follows Subject-Object-Verb (SOV) order (e.g., "मैं सेब खाता हूँ" / "I apple eat").
*   **Verb conjugation:** Verbs conjugate based on gender, number, person, and tense. The auxiliary verb changes to match the subject.
*   **Gender agreement:** Hindi has two genders (masculine and feminine). Adjectives and verbs must agree with the gender of the noun they modify (e.g., "बड़ा लड़का" / big boy vs. "बड़ी लड़की" / big girl).
*   **Plural formation:** Noun endings change depending on gender and case (e.g., "लड़का" (boy) -> "लड़के" (boys); "किताब" (book) -> "किताबें" (books)).
*   **Tense and aspect:** Relies heavily on auxiliary verbs (होना - to be) to indicate tense and aspect (continuous, perfect).
*   **Case system:** Hindi uses postpositions (like prepositions but placed *after* the noun) rather than a strict inflectional case system, though nouns do take an oblique form before postpositions.

### 2. PUNCTUATION RULES
*   **Quotation marks:** Double quotes (" ") and single quotes (' ') are used similarly to English.
*   ⚠️ **Comma and period:** Commas are used as in English. However, the period is replaced by the *poorna viram* or danda (।) to mark the end of a sentence.
*   **Space before/after:** No space before punctuation marks (, ; : ! ? ।); one space after.
*   **Ellipsis formatting:** Standard three dots (...) with no spaces between them.
*   **Exclamation and question mark:** Used identically to English (! ?).
*   **Hyphen and dash:** Hyphens (-) are used for compound words; em-dashes (—) for breaks in thought.

### 3. FORMATTING RULES
*   **Date format:** DD/MM/YYYY (e.g., 15/08/2023).
*   **Time format:** Both 12-hour (with AM/PM equivalents: सुबह/पूर्वाह्न and शाम/अपराह्न) and 24-hour formats are understood, but 12-hour is more common in daily text.
*   ⚠️ **Number formatting:** Indian numbering system is preferred (Lakhs and Crores). Separators: 1,00,000.00 (comma for thousands/lakhs, period for decimals).
*   **Currency symbol placement:** The Rupee symbol (₹) precedes the amount without a space (e.g., ₹500).
*   **Measurement units:** Metric system (kg, km, cm). 
*   **Address format:** Smallest to largest entity (Name, Flat/House No, Street, Locality, City, PIN code, State).

### 4. TYPOGRAPHY RULES
*   **Script direction:** Left-to-Right (LTR).
*   ⚠️ **Capitalization:** The Devanagari script does *not* have uppercase or lowercase letters. Title case or sentence case concepts do not apply.
*   **Bold and italic:** Used for emphasis, though italics can sometimes render poorly in certain Devanagari fonts.
*   **Line breaking:** Words should not be broken arbitrarily. Line breaks should occur at spaces.
*   ⚠️ **Special characters:** The *nukta* (a dot below a character like ज़, फ़) is used for loan words (mostly from Persian/Arabic/English) to represent sounds like 'z' and 'f'.

### 5. TRANSLATION RULES
*   ⚠️ **Formality levels:** Three tiers of second-person pronouns: "तू" (tu - intimate/informal), "तुम" (tum - familiar), and "आप" (aap - formal/respectful). UI and business text must default to "आप" (aap).
*   **False friends:** Avoid overliteral translation of English idioms (e.g., "piece of cake" should be translated to "बाएँ हाथ का खेल", not "केक का टुकड़ा").
*   **Brand names:** Keep brand names in English or transliterate them into Devanagari based on client preference. Do not translate them (e.g., "Apple" the company is "ऐप्पल", not "सेब").
*   **Loan words:** Common English technical terms (e.g., Computer, Internet, Download) are often transliterated (कंप्यूटर, इंटरनेट, डाउनलोड) rather than strictly translated into obscure Sanskritized Hindi.

### 6. SUBTITLING RULES
*   **Maximum characters per line:** 35-40 characters.
*   **Maximum lines per subtitle:** 2 lines.
*   **Reading speed:** 15-17 characters per second (CPS).
*   **Line breaks:** Break at logical linguistic pauses (e.g., before postpositions or conjunctions), not in the middle of a compound word.
*   **Speaker ID:** Formatted in brackets or with a colon: [अनाउंसर] or अनाउंसर:

### 7. TRANSCRIPTION RULES
*   **Filler words:** Unless strict verbatim is requested, omit umms and ahhs (e.g., उम्म, अह).
*   **Overlapping speech:** Mark with brackets [दोनों एक साथ बोलते हैं] or standard timestamp overlays.
*   **Timestamps:** [HH:MM:SS] format.
*   **Inaudible:** Use [अस्पष्ट] for inaudible segments.
*   **Numbers:** Spell out numbers 1-10 (एक, दो); use digits for 11 and above unless at the beginning of a sentence.

### 8. CULTURAL & LOCALIZATION NOTES
*   🌐 **Sensitivities:** Avoid highly Sanskritized Hindi (Shuddh Hindi) for general UI/SaaS copy; prefer "Hinglish" or conversational Hindi (e.g., use "लॉगिन" for login, not "प्रवेश करें").
*   🌐 **Religion/Politics:** Maintain strict neutrality. Use respectful titles for historical or political figures if context demands it.

### 9. QA CHECK PRIORITIES
*   🔍 **Danda Usage:** Ensure the *poorna viram* (।) is used instead of the English period (.), and check that no extra space precedes it.
*   🔍 **Formality Consistency:** Verify that "आप" (aap) is used consistently in verbs (e.g., "करें", not "करो").
*   🔍 **Nukta Check:** Ensure proper use of nuktas in standard transliterations (e.g., "ज़रूरत" instead of "जरूरत").

---

## Bengali (Bangla)
### Implementation Status: Implemented in ErrorSweep

### 1. GRAMMAR RULES
*   ⚠️ **Sentence structure:** Subject-Object-Verb (SOV) order (e.g., "আমি বই পড়ি" / I book read).
*   **Verb conjugation:** Verbs conjugate strictly according to person (1st, 2nd, 3rd) and formality level (intimate, familiar, formal). They do *not* conjugate for number or gender.
*   **Gender agreement:** Bengali grammar does not have grammatical gender for inanimate objects. Adjectives do not change based on gender.
*   **Plural formation:** Uses suffixes like -রা (-ra), -গুলি (-guli), -গুলো (-gulo) added to nouns (e.g., "ছেলে" / boy -> "ছেলেরা" / boys).
*   **Tense and aspect:** Highly structured with specific verb endings for simple, continuous, and perfect aspects across past, present, and future.

### 2. PUNCTUATION RULES
*   **Quotation marks:** Double quotes (" ") are standard.
*   ⚠️ **Comma and period:** Uses the danda (।) for a full stop, identical to Hindi. Commas (,) are used as in English.
*   **Space before/after:** No space before a danda (।), comma, or question mark; one space after.
*   **Exclamation and question mark:** Standard (! ?).

### 3. FORMATTING RULES
*   **Date format:** DD/MM/YYYY.
*   **Time format:** 12-hour with (সকাল/AM, দুপুর/Noon, বিকেল/PM, রাত/Night) or 24-hour.
*   ⚠️ **Number formatting:** Indian numbering system (Lakhs and Crores).
*   ⚠️ **Currency:** The Taka symbol (৳) is placed before the amount (e.g., ৳৫০০ / ৳500).

### 4. TYPOGRAPHY RULES
*   **Script direction:** Left-to-Right (LTR).
*   ⚠️ **Capitalization:** No concept of uppercase or lowercase in the Bengali script.
*   **Line breaking:** Break at word boundaries (spaces).
*   **Special characters:** Features complex conjunct consonants (যুক্তাক্ষর) which must render correctly without breaking (e.g., ক + ষ = ক্ষ).

### 5. TRANSLATION RULES
*   ⚠️ **Formality levels:** Three tiers of second-person pronouns: "তুই" (tui - intimate), "তুমি" (tumi - familiar), and "আপনি" (apni - formal). UI and professional text must use "আপনি".
*   **Brand names:** Keep in English or transliterate (e.g., "Google" -> "গুগল").
*   **Loan words:** Heavy integration of English tech terms (e.g., "Download" -> "ডাউনলোড"). Do not use archaic terms just to avoid English.

### 6. SUBTITLING RULES
*   **Maximum characters per line:** 35-40 characters.
*   **Maximum lines per subtitle:** 2 lines.
*   **Reading speed:** 15-17 CPS.
*   **Speaker ID:** [স্পিকারের নাম]: or স্পিকার:

### 7. TRANSCRIPTION RULES
*   **Filler words:** Omit standard fillers unless strict verbatim.
*   **Inaudible:** Use [অস্পষ্ট].

### 8. CULTURAL & LOCALIZATION NOTES
*   🌐 **Dialect boundaries:** Ensure standard vocabulary (Sadhu or standard Cholit) is used unless specific regional targeting (e.g., Bangladesh vs. West Bengal, India) is requested. Standard UI uses Cholit bhasha.

### 9. QA CHECK PRIORITIES
*   🔍 **Verb-Pronoun Agreement:** A critical error is mixing formal pronouns with familiar verb endings (e.g., "আপনি করো" is incorrect; it must be "আপনি করুন").
*   🔍 **Font Rendering:** Check conjunct characters (e.g., ঙ্গ, ঞ্জ) to ensure the font engine hasn't broken them into individual components with a halant/hasant.

---

## Tamil
### Implementation Status: Implemented in ErrorSweep

### 1. GRAMMAR RULES
*   ⚠️ **Sentence structure:** Strictly Subject-Object-Verb (SOV) (e.g., "நான் புத்தகம் படிக்கிறேன்" / I book read).
*   **Verb conjugation:** Verbs conjugate for tense, person, number, and rational/irrational gender classes.
*   ⚠️ **Gender/Noun classes:** Tamil categorizes nouns into "Rational" (uyarthinai - gods, humans) and "Irrational" (akrinai - animals, objects).
*   **Plural formation:** Suffixes like -கள் (-kal) are appended (e.g., "மரம்" / tree -> "மரங்கள்" / trees).
*   **Agglutination:** Highly agglutinative. Prepositions are attached as suffixes to the end of nouns (e.g., "in the house" -> "வீட்டில்").

### 2. PUNCTUATION RULES
*   **Comma and period:** Uses the standard English period (.) for a full stop. It does *not* use the danda (।).
*   **Space before/after:** No space before punctuation, one space after.
*   **Hyphen and dash:** Standard usage, though agglutination reduces the need for hyphens in compound words.

### 3. FORMATTING RULES
*   **Date format:** DD/MM/YYYY.
*   **Time format:** 12-hour or 24-hour.
*   **Number formatting:** Indian numbering system (Lakhs/Crores). Comma for thousands, period for decimals.
*   **Currency:** Rupee symbol (₹) before the number.

### 4. TYPOGRAPHY RULES
*   **Script direction:** Left-to-Right (LTR).
*   ⚠️ **Capitalization:** No uppercase/lowercase distinctions.
*   **Word spacing:** Because Tamil is agglutinative, words can become extremely long. Proper word boundaries must be respected.

### 5. TRANSLATION RULES
*   ⚠️ **Formality levels:** Second-person singular "நீ" (Nee - informal) vs "நீங்கள்" (Neengal - formal/plural). UI requires "நீங்கள்".
*   **Tone:** Tamil has distinct formal/written (Senthamizh) and spoken (Koduntamil) registers. SaaS and UI translation generally uses a modern, simplified formal register.
*   **Transliteration vs Translation:** While Tamil has a pure translation for almost every tech term, users prefer English transliterations for UI elements (e.g., "கிளிக் செய்யவும்" / Click vs "அழுத்தவும்" / Press).

### 6. SUBTITLING RULES
*   ⚠️ **Maximum characters per line:** 40-45 characters (Tamil words are physically longer due to agglutination).
*   **Maximum lines per subtitle:** 2 lines.
*   **Reading speed:** 15-18 CPS.

### 7. TRANSCRIPTION RULES
*   **Inaudible:** Use [கேட்கவில்லை] or [தெளிவாக இல்லை].

### 8. CULTURAL & LOCALIZATION NOTES
*   🌐 **Sensitivities:** Avoid highly localized Chennai slang unless requested. Maintain respectful suffixes (-ஆர்/-அவர்கள்) when referring to esteemed individuals.

### 9. QA CHECK PRIORITIES
*   🔍 **Length Expansion:** Tamil strings often expand by 40-60% compared to English. QA must heavily check for text truncation in buttons and menus.
*   🔍 **Formality (Neengal):** Ensure all calls to action end in the formal/respectful imperative "-வும்" (e.g., "சேமிக்கவும்" / Please save).

---

## Telugu
### Implementation Status: Implemented in ErrorSweep

### 1. GRAMMAR RULES
*   ⚠️ **Sentence structure:** Subject-Object-Verb (SOV) order (e.g., "నేను అన్నం తిన్నాను" / I rice ate).
*   **Agglutination:** Like Tamil, Telugu is highly agglutinative. Case markers and postpositions are attached to the noun stem (e.g., "ఇంటిలో" / in the house).
*   **Verb conjugation:** Verbs agree with the subject in person, number, and gender.
*   **Gender:** Distinguishes between masculine and non-masculine (feminine and neuter) in the singular, but merges masculine and feminine in the plural.
*   **Plural formation:** Suffixes like -లు (-lu) or -ళ్లు (-llu) (e.g., "పుస్తకం" / book -> "పుస్తకాలు" / books).

### 2. PUNCTUATION RULES
*   **Comma and period:** Uses the English period (.) for full stops, not the danda.
*   **Space before/after:** Standard English spacing (no space before, one space after).

### 3. FORMATTING RULES
*   **Date format:** DD/MM/YYYY.
*   **Number formatting:** Indian numbering system (Lakhs, Crores).
*   **Currency:** Rupee symbol (₹) before the number.

### 4. TYPOGRAPHY RULES
*   **Script direction:** Left-to-Right (LTR).
*   ⚠️ **Capitalization:** No uppercase/lowercase.
*   ⚠️ **Zero Width Non-Joiner (ZWNJ):** Highly critical in Telugu. English loanwords taking Telugu suffixes must be separated by a ZWNJ (e.g., "పాస్‌వర్డ్‌ను" / password-nu) to prevent the font engine from incorrectly fusing the English word's final consonant with the Telugu suffix.

### 5. TRANSLATION RULES
*   ⚠️ **Formality levels:** Second-person "నువ్వు" (Nuvvu - informal) vs "మీరు" (Meeru - formal/plural). UI uses "మీరు".
*   **Imperative forms:** UI commands must use the respectful imperative ending "-అండి" (-andi). E.g., "Save" -> "సేవ్ చేయండి".

### 6. SUBTITLING RULES
*   **Maximum characters per line:** 35-40.
*   **Maximum lines per subtitle:** 2.
*   **Reading speed:** 15-18 CPS.

### 7. TRANSCRIPTION RULES
*   **Inaudible:** Use [వినపడటం లేదు].

### 8. CULTURAL & LOCALIZATION NOTES
*   🌐 **Loanwords:** Telugu speakers heavily use English tech terms. Do not force Sanskrit-derived terms for concepts like "Dashboard" or "Password". Use "డాష్‌బోర్డ్" and "పాస్‌వర్డ్".

### 9. QA CHECK PRIORITIES
*   🔍 **ZWNJ Integrity:** The most critical QA check for Telugu SaaS localization. Ensure ZWNJ is present between English loan words and Telugu suffixes (e.g., "ఫైల్‌ను", not "ఫైల్ను").
*   🔍 **Imperative Verification:** Check that all UI buttons use the "-అండి" (andi) suffix.

---

## Kannada
### Implementation Status: Implemented in ErrorSweep

### 1. GRAMMAR RULES
*   ⚠️ **Sentence structure:** Subject-Object-Verb (SOV).
*   **Agglutination:** Highly agglutinative; modifiers attach as suffixes.
*   **Gender:** Three genders: masculine, feminine, and neuter.
*   **Plural formation:** Suffixes -ಗಳು (-galu) or -ರು (-ru) (e.g., "ಮರ" / tree -> "ಮರಗಳು" / trees).

### 2. PUNCTUATION RULES
*   **Period:** Uses the English period (.).
*   **Quotes:** Double quotes (" ") are standard.

### 3. FORMATTING RULES
*   **Date format:** DD/MM/YYYY.
*   **Number formatting:** Indian system (Lakhs, Crores).

### 4. TYPOGRAPHY RULES
*   **Script direction:** Left-to-Right (LTR).
*   ⚠️ **Capitalization:** No uppercase/lowercase.

### 5. TRANSLATION RULES
*   ⚠️ **Formality levels:** "ನೀನು" (Neenu - informal) vs "ನೀವು" (Neevu - formal/plural). UI defaults to "ನೀವು".
*   **Imperative verbs:** Use the formal command suffix "-ಇರಿ" (-iri) or "-ಮಾಡಿ" (maadi) (e.g., "Save" -> "ಸೇವ್ ಮಾಡಿ").

### 6. SUBTITLING & TRANSCRIPTION RULES
*   **Line limits:** 35-40 characters max.
*   **Inaudible tag:** [ಕೇಳಿಸುತ್ತಿಲ್ಲ].

### 7. QA CHECK PRIORITIES
*   🔍 **Text Expansion:** Like Tamil and Telugu, Kannada expands significantly. Truncation checks are mandatory.
*   🔍 **Orthography:** Ensure complex vowel signs and half-consonants render correctly without breaking.

---

## Malayalam
### Implementation Status: Implemented in ErrorSweep

### 1. GRAMMAR RULES
*   ⚠️ **Sentence structure:** Subject-Object-Verb (SOV) order.
*   **Agglutination:** Highly agglutinative. Nouns and verbs take multiple suffixes to denote case, tense, and person.
*   **Gender:** Grammatical gender is based on rationality (rational/human vs. irrational/non-human) rather than strict masculine/feminine for inanimate objects.
*   **Plural formation:** Suffixes such as -കൾ (-kal) or -മാർ (-mar) are added depending on the noun class.

### 2. PUNCTUATION RULES
*   **Comma and period:** Uses the standard English period (.) for full stops. Does not use the danda.
*   **Space before/after:** No space before punctuation; one space after.

### 3. FORMATTING RULES
*   **Date format:** DD/MM/YYYY.
*   **Number formatting:** Indian numbering system (Lakhs, Crores). Comma for thousands, period for decimals.
*   **Currency:** Rupee symbol (₹) before the number.

### 4. TYPOGRAPHY RULES
*   **Script direction:** Left-to-Right (LTR).
*   ⚠️ **Capitalization:** No uppercase/lowercase.
*   ⚠️ **Chillu Letters:** Malayalam has special consonant forms called "Chillu" letters (e.g., ർ, ൽ). Modern Unicode encodes these atomically, but legacy systems used Zero Width Joiners (ZWJ). Ensure modern atomic Unicode characters are used to prevent rendering bugs.

### 5. TRANSLATION RULES
*   ⚠️ **Formality levels:** "നീ" (Nee - informal) vs "നിങ്ങൾ" (Ningal - formal/plural) vs "താങ്കൾ" (Thaangal - highly formal). UI text should default to "നിങ്ങൾ" (Ningal).
*   **Word Length:** Due to agglutination, translated words can be exceptionally long (e.g., "ഉപയോഗിക്കുക" for "use"). 

### 6. SUBTITLING RULES
*   **Maximum characters per line:** 35-40 characters (adjusted for longer word widths).
*   **Maximum lines per subtitle:** 2 lines.
*   **Reading speed:** 15-18 CPS.

### 7. TRANSCRIPTION RULES
*   **Inaudible:** Use [വ്യക്തമല്ല].

### 8. CULTURAL & LOCALIZATION NOTES
*   🌐 **Sensitivities:** Malayalam speakers prefer a respectful, slightly formal tone in professional software. Avoid overly colloquial slang in UI text.

### 9. QA CHECK PRIORITIES
*   🔍 **UI Expansion:** Severe risk of text truncation in buttons and menus.
*   🔍 **Font Rendering:** Verify that conjuncts and Chillu characters do not break into base letters + virama.

---

## Marathi
### Implementation Status: Implemented in ErrorSweep

### 1. GRAMMAR RULES
*   ⚠️ **Sentence structure:** Subject-Object-Verb (SOV) order.
*   **Verb conjugation:** Verbs agree with the subject in gender, number, and person.
*   ⚠️ **Gender agreement:** Unlike Hindi, Marathi retains *three* genders: Masculine, Feminine, and Neuter. This heavily affects adjective and verb agreement.
*   **Case system:** Uses postpositions that attach directly to the noun, placing the noun in an oblique case.

### 2. PUNCTUATION RULES
*   ⚠️ **Comma and period:** Unlike Hindi (which uses the danda), modern Marathi heavily favors the English period (.) for full stops, especially in digital and UI text.
*   **Space before/after:** Standard English spacing.

### 3. FORMATTING RULES
*   **Date format:** DD/MM/YYYY.
*   **Number formatting:** Indian numbering system (Lakhs, Crores).

### 4. TYPOGRAPHY RULES
*   **Script direction:** Left-to-Right (LTR) using the Devanagari script.
*   ⚠️ **Special Characters:** Marathi makes heavy use of the retroflex lateral consonant "ळ" (Lla), which is absent in standard Hindi.

### 5. TRANSLATION RULES
*   ⚠️ **Formality levels:** "तू" (Tu - informal), "तुम्ही" (Tumhi - formal/plural), and "आपण" (Aapan - highly respectful/inclusive). SaaS UI defaults to "तुम्ही" (Tumhi).
*   **Loan words:** Common tech terms are transliterated (e.g., पासवर्ड for password).

### 6. SUBTITLING RULES
*   **Line limits:** 35-40 characters.
*   **Reading speed:** 15-17 CPS.

### 7. TRANSCRIPTION RULES
*   **Inaudible:** Use [अस्पष्ट].

### 8. CULTURAL & LOCALIZATION NOTES
*   🌐 **Vocabulary:** Avoid "Hindi-izing" Marathi. Ensure authentic Marathi vocabulary is used (e.g., using "आहे" correctly instead of Hindi structures).

### 9. QA CHECK PRIORITIES
*   🔍 **Period Usage:** Ensure the English period (.) is used at the end of sentences, not the Hindi danda (।), unless strictly requested by the client.
*   🔍 **Gender Agreement:** Verify neuter gender agreements, which are a common error point for translators accustomed to Hindi.

---

## Gujarati
### Implementation Status: Implemented in ErrorSweep

### 1. GRAMMAR RULES
*   ⚠️ **Sentence structure:** Subject-Object-Verb (SOV) order.
*   **Gender:** Three genders: Masculine, Feminine, and Neuter.
*   **Verb conjugation:** Verbs agree with gender, number, and person.

### 2. PUNCTUATION RULES
*   ⚠️ **Comma and period:** Uses the English period (.) for a full stop, not the danda.
*   **Space before/after:** Standard English spacing.

### 3. FORMATTING RULES
*   **Date format:** DD/MM/YYYY.
*   **Number formatting:** Indian numbering system.

### 4. TYPOGRAPHY RULES
*   **Script direction:** Left-to-Right (LTR).
*   ⚠️ **Script specific:** Uses the Gujarati script, which lacks the top horizontal line (shirorekha) found in Devanagari.

### 5. TRANSLATION RULES
*   ⚠️ **Formality levels:** "તું" (Tu - informal), "તમે" (Tame - formal), "આપ" (Aap - highly formal). UI defaults to "તમે" (Tame).

### 6. SUBTITLING RULES
*   **Line limits:** 35-40 characters.

### 7. TRANSCRIPTION RULES
*   **Inaudible:** Use [અસ્પષ્ટ].

### 8. CULTURAL & LOCALIZATION NOTES
*   🌐 **Business Tone:** Gujarati localization for SaaS often leans heavily on English transliteration for business and tech terms to sound modern and professional.

### 9. QA CHECK PRIORITIES
*   🔍 **Full Stop:** Ensure periods (.) are used instead of Devanagari dandas.
*   🔍 **Formality:** Check consistency of "તમે" across all verbs and pronouns.

---

## Punjabi (Gurmukhi)
### Implementation Status: Implemented in ErrorSweep

### 1. GRAMMAR RULES
*   ⚠️ **Sentence structure:** Subject-Object-Verb (SOV) order.
*   ⚠️ **Tonal language:** Punjabi is unique among Indo-Aryan languages as it is tonal. Tones are often indicated by specific consonant choices or orthographic markers.
*   **Gender:** Two genders (Masculine, Feminine).

### 2. PUNCTUATION RULES
*   ⚠️ **Period:** Uses the danda (।) for a full stop, similar to Hindi.
*   **Space before/after:** No space before a danda, one space after.

### 3. FORMATTING RULES
*   **Date format:** DD/MM/YYYY.

### 4. TYPOGRAPHY RULES
*   **Script direction:** Left-to-Right (LTR) using the Gurmukhi script.
*   ⚠️ **Diacritics:** Heavy reliance on nasalization marks like *Bindi* (ਂ) and *Tippi* (ੰ), as well as the *Adhak* (ੱ) which doubles the following consonant.

### 5. TRANSLATION RULES
*   ⚠️ **Formality levels:** "ਤੂੰ" (Tu - informal) vs "ਤੁਸੀਂ" (Tusi - formal). UI uses "ਤੁਸੀਂ" (Tusi).

### 6. SUBTITLING RULES
*   **Speaker ID:** [ਸਪੀਕਰ]:

### 7. TRANSCRIPTION RULES
*   **Inaudible:** Use [ਅਸਪਸ਼ਟ].

### 9. QA CHECK PRIORITIES
*   🔍 **Danda Usage:** Ensure (।) is used instead of (.).
*   🔍 **Nasalization:** Missing Bindi or Tippi marks completely change word meanings. QA must heavily verify diacritics.

---

## Urdu
### Implementation Status: Implemented in ErrorSweep

### 1. GRAMMAR RULES
*   ⚠️ **Sentence structure:** Subject-Object-Verb (SOV) order. Grammatically mutually intelligible with Hindi at a conversational level.
*   **Gender:** Two genders (Masculine, Feminine).

### 2. PUNCTUATION RULES
*   ⚠️ **RTL Punctuation:** Uses the Arabic comma (،) and Arabic question mark (؟). 
*   ⚠️ **Period:** Uses the standard period (.) or the Urdu khatma (۔), though the standard period is most widely accepted in digital SaaS UI.
*   **Space before/after:** No space before punctuation; one space after.

### 3. FORMATTING RULES
*   **Date format:** DD/MM/YYYY.
*   ⚠️ **Number formatting:** Can use standard digits (1, 2, 3) or Eastern Arabic/Urdu numerals (۱, ۲, ۳) depending on client preference. Default to standard (1, 2, 3) for software UI.

### 4. TYPOGRAPHY RULES
*   ⚠️ **Script direction:** Right-to-Left (RTL).
*   ⚠️ **Font Style:** Urdu must be rendered in the *Nastaliq* script style (flowing, diagonal), NOT the *Naskh* style used for Arabic. Naskh is considered difficult to read by native Urdu speakers.
*   **Capitalization:** No uppercase/lowercase.

### 5. TRANSLATION RULES
*   ⚠️ **Formality levels:** "تو" (Tu - intimate), "تم" (Tum - familiar), "آپ" (Aap - formal). UI must use "آپ" (Aap).
*   **Vocabulary:** Avoid overly Persianized or Arabicized vocabulary for general SaaS; aim for natural, accessible Urdu.

### 6. SUBTITLING RULES
*   **Maximum characters per line:** 35-40 characters.

### 7. QA CHECK PRIORITIES
*   🔍 **RTL Directionality:** Ensure numbers, English loan words, and placeholders do not break the RTL flow (e.g., LRM/RLM marker issues).
*   🔍 **Punctuation:** Strictly enforce the Arabic comma (،) and question mark (؟) instead of English (,) and (?).

---

## English (UK vs. US)
### Implementation Status: Implemented in ErrorSweep

### 1. GRAMMAR RULES
*   **Sentence structure:** Subject-Verb-Object (SVO).
*   **Gender:** No grammatical gender for inanimate nouns.
*   **Plurals:** Generally formed by adding -s or -es.
*   ⚠️ **Collective Nouns (UK vs US):** UK treats collective nouns as plural (e.g., "The team *are* winning"). US treats them as singular (e.g., "The team *is* winning").

### 2. PUNCTUATION RULES
*   ⚠️ **Quotation marks (US):** Double quotes (" ") are primary. Punctuation goes *inside* the quotes (e.g., He said, "Hello.")
*   ⚠️ **Quotation marks (UK):** Single quotes (' ') are primary. Punctuation goes *outside* the quotes unless part of the quote (e.g., He said, 'Hello'.)
*   **Oxford Comma:** Highly preferred in US English (A, B, and C); optional but less common in UK English unless required for clarity.

### 3. FORMATTING RULES
*   ⚠️ **Date format (US):** MM/DD/YYYY (e.g., 12/31/2023).
*   ⚠️ **Date format (UK):** DD/MM/YYYY (e.g., 31/12/2023).
*   ⚠️ **Time format:** US strictly uses 12-hour AM/PM. UK mixes 12-hour informally and 24-hour formally.
*   **Number formatting:** 1,000.00 (Comma for thousands, period for decimals).

### 4. TYPOGRAPHY RULES
*   **Capitalization:** Title Case (Capitalize Every Major Word) is common for US headings. Sentence case (Capitalize only the first word) is increasingly the standard globally for UI.

### 5. TRANSLATION RULES
*   **Formality:** "You" is universal. Formality is conveyed through vocabulary, not pronouns.
*   ⚠️ **Spelling Variations:**
    *   US: -ize (customize), -or (color), -er (center).
    *   UK: -ise (customise), -our (colour), -re (centre).

### 6. SUBTITLING RULES
*   **Maximum characters per line:** 42 characters.
*   **Reading speed:** 15-21 CPS.

### 9. QA CHECK PRIORITIES
*   🔍 **Locale Consistency:** Ensure no mixing of US (-ize) and UK (-ise) spellings within the same project.
*   🔍 **Date Formats:** Critical QA check for US vs UK date ambiguity.

---

## French
### Implementation Status: Implemented in ErrorSweep

### 1. GRAMMAR RULES
*   **Sentence structure:** Subject-Verb-Object (SVO).
*   **Gender:** Two genders (Masculine, Feminine). Adjectives and articles must agree.
*   **Adjective Placement:** Most adjectives come *after* the noun (e.g., "un chat noir" / a cat black), unlike English.

### 2. PUNCTUATION RULES
*   ⚠️ **Space before punctuation:** A non-breaking space (NBSP) is strictly required before double-element punctuation marks: colon (:), semicolon (;), exclamation mark (!), and question mark (?).
*   ⚠️ **Quotation marks:** Uses guillemets (« ») with a non-breaking space inside both brackets (e.g., « Bonjour »).

### 3. FORMATTING RULES
*   **Date format:** DD/MM/YYYY.
*   **Time format:** 24-hour clock, using 'h' as a separator (e.g., 14h30).
*   ⚠️ **Number formatting:** Space (often non-breaking) for thousands, comma for decimals (e.g., 1 000,50).
*   **Currency:** Placed *after* the number with a space (e.g., 10,00 €).

### 4. TYPOGRAPHY RULES
*   **Capitalization:** Sentence case is standard for titles and headers (e.g., "Tableau de bord" not "Tableau De Bord").
*   ⚠️ **Accents on Uppercase:** Accents must be preserved on capital letters (e.g., "À propos", "ÉTAT").

### 5. TRANSLATION RULES
*   ⚠️ **Formality levels:** "Tu" (informal/singular) vs "Vous" (formal/plural). SaaS and B2B software strictly defaults to "Vous". Modern B2C apps sometimes use "Tu". Must follow client instructions.
*   **False friends:** e.g., "Actuellement" means *currently*, not *actually*. "Assister" means *to attend*, not *to assist*.

### 6. SUBTITLING RULES
*   **Maximum characters per line:** 38-42.
*   **Reading speed:** 15-18 CPS.

### 8. CULTURAL & LOCALIZATION NOTES
*   🌐 **Regional Differences:** Canadian French (fr-CA) does *not* put a space before punctuation marks like !, ?, and ;, unlike European French.

### 9. QA CHECK PRIORITIES
*   🔍 **Punctuation Spacing:** Missing NBSP before `! ? : ;` is a critical formatting failure in fr-FR.
*   🔍 **Tu/Vous Consistency:** Mixing "tu" and "vous" in the same paragraph or UI flow is a critical QA failure.

---

## German
### Implementation Status: Implemented in ErrorSweep

### 1. GRAMMAR RULES
*   ⚠️ **Sentence structure:** SVO in main clauses, but verbs move to the end of the sentence in subordinate clauses (SOV). Compound verbs are split (e.g., "Ich *mache* die Tür *auf*").
*   **Gender:** Three genders (Masculine, Feminine, Neuter).
*   **Cases:** Four cases (Nominative, Accusative, Dative, Genitive), dictating article and adjective endings.

### 2. PUNCTUATION RULES
*   ⚠️ **Quotation marks:** Uses low opening and high closing quotes („...“). Alternatively, French-style guillemets pointing inward (»...«) are used in publishing.
*   **Space before/after:** Standard English spacing (no space before `!`, `?`, etc.).

### 3. FORMATTING RULES
*   **Date format:** DD.MM.YYYY (e.g., 31.12.2023).
*   **Time format:** 24-hour clock (e.g., 14:30 Uhr).
*   ⚠️ **Number formatting:** Period for thousands, comma for decimals (e.g., 1.000,50).
*   **Currency:** Placed after the number with a space (e.g., 10,00 €).

### 4. TYPOGRAPHY RULES
*   ⚠️ **Capitalization:** ALL nouns are capitalized, regardless of where they appear in the sentence (e.g., "Das ist ein schönes Haus").
*   **Compound words:** German combines words into single, long compound nouns without spaces (e.g., "Benutzerkontosteuerung").

### 5. TRANSLATION RULES
*   ⚠️ **Formality levels:** "Du" (informal) vs "Sie" (formal). Historically, UI used "Sie". Modern tech/SaaS often shifts to "Du". Client instruction is absolutely required. If "Sie" is used, it *must* be capitalized, or it means "she/they".

### 6. SUBTITLING RULES
*   **Maximum characters per line:** 38-42. Word lengths are long, requiring aggressive condensing.

### 8. CULTURAL & LOCALIZATION NOTES
*   🌐 **Gender-neutral language:** Increasingly important. Uses the "Binnen-I" (MitarbeiterInnen), asterisk (Mitarbeiter*innen), or colon (Mitarbeiter:innen) to be inclusive.

### 9. QA CHECK PRIORITIES
*   🔍 **Noun Capitalization:** Lowercase nouns are a critical spelling error.
*   🔍 **UI Truncation:** German compound nouns will break fixed-width UI elements.

---

## Spanish (Spain & Latin America)
### Implementation Status: Implemented in ErrorSweep

### 1. GRAMMAR RULES
*   **Sentence structure:** Subject-Verb-Object (SVO). 
*   ⚠️ **Pro-drop:** Subject pronouns (yo, tú, él) are usually omitted because the verb ending implies the subject (e.g., "Tengo un coche" instead of "Yo tengo un coche").
*   **Gender:** Two genders (Masculine, Feminine).
*   **Adjectives:** Generally placed after the noun (e.g., "el botón rojo").

### 2. PUNCTUATION RULES
*   ⚠️ **Inverted marks:** Questions and exclamations MUST begin with inverted marks (¿?, ¡!). E.g., "¿Estás seguro?".
*   ⚠️ **Quotation marks:** Spain often uses angular quotes («...»). Latin America generally uses English-style double quotes ("...").

### 3. FORMATTING RULES
*   **Date format:** DD/MM/YYYY.
*   ⚠️ **Number formatting:** 
    *   Spain: Period for thousands, comma for decimals (1.000,50).
    *   Latin America (Mexico): Comma for thousands, period for decimals (1,000.50).
*   **Currency:** Spain (10,00 €). LatAm ($1,000.00).

### 4. TYPOGRAPHY RULES
*   **Capitalization:** Sentence case. ⚠️ Days of the week, months, and languages are lowercase (e.g., lunes, enero, español).

### 5. TRANSLATION RULES
*   ⚠️ **Formality levels & Regional variations:**
    *   **Spain:** "Tú" (informal sing.), "Usted" (formal sing.), "Vosotros" (informal plural), "Ustedes" (formal plural).
    *   **LatAm:** "Tú" or "Vos" (informal sing., 'vos' heavily used in Argentina/Uruguay), "Usted" (formal sing.), "Ustedes" (plural, both formal and informal; 'vosotros' is not used).
    *   **UI Standard:** Universal Latin American Spanish for tech often defaults to "tú" and "ustedes".
*   **Vocabulary differences:** Computer is "Ordenador" (Spain) vs. "Computadora" (LatAm). File is "Fichero" (Spain) vs. "Archivo" (LatAm).

### 6. SUBTITLING RULES
*   **Maximum characters per line:** 42.
*   **Reading speed:** 15-18 CPS.

### 8. CULTURAL & LOCALIZATION NOTES
*   🌐 **Localization targeting:** Never mix Spain vocabulary with Latin American grammar. Choose the specific target locale.

### 9. QA CHECK PRIORITIES
*   🔍 **Inverted Punctuation:** Missing opening `¿` or `¡` is a strict QA failure.
*   🔍 **Capitalization:** Capitalizing months or days (e.g., Lunes) is a spelling error.

---

## Italian
### Implementation Status: Implemented in ErrorSweep

### 1. GRAMMAR RULES
*   **Sentence structure:** Subject-Verb-Object (SVO), but highly flexible due to verb inflection.
*   ⚠️ **Pro-drop:** Subject pronouns (io, tu, lui) are usually omitted (e.g., "Vado al cinema" instead of "Io vado al cinema").
*   **Gender:** Two genders (Masculine, Feminine). Adjectives and articles must agree with the noun.
*   **Adjectives:** Most descriptive adjectives are placed *after* the noun (e.g., "la macchina rossa" / the red car).

### 2. PUNCTUATION RULES
*   ⚠️ **Quotation marks:** Traditional publishing uses guillemets (« ») without internal spaces (unlike French). However, double quotes (" ") are widely accepted in digital/UI text.
*   **Space before/after:** Standard English spacing (no space before `?`, `!`, `:`, `;`).

### 3. FORMATTING RULES
*   **Date format:** DD/MM/YYYY (e.g., 31/12/2023).
*   **Time format:** 24-hour clock separated by a dot or colon (e.g., 14.30 or 14:30).
*   ⚠️ **Number formatting:** Period for thousands, comma for decimals (e.g., 1.000,50).
*   **Currency:** The Euro symbol (€) is placed *after* the amount with a space (e.g., 10,00 €).

### 4. TYPOGRAPHY RULES
*   **Capitalization:** Sentence case is standard for titles and headers (e.g., "Impostazioni del profilo" not "Impostazioni Del Profilo").
*   ⚠️ **Accents:** Must distinguish between grave (è, à) and acute (é, í) accents. E.g., "perché", not "perchè".

### 5. TRANSLATION RULES
*   ⚠️ **Formality levels:** "Tu" (informal/singular) vs "Lei" (formal/singular). In B2B SaaS, "Lei" is common. In modern B2C apps, "Tu" is preferred. 
*   ⚠️ **Pronoun Capitalization:** When using the formal "Lei" (or "Le", "Suo"), it is traditionally capitalized in written text to distinguish it from "lei" (she/her), though lowercase is becoming acceptable in casual UI. Follow client style guides.

### 6. SUBTITLING RULES
*   **Maximum characters per line:** 38-42.
*   **Reading speed:** 15-18 CPS.

### 8. CULTURAL & LOCALIZATION NOTES
*   🌐 **Loan words:** Italian tech culture heavily adopts English terms (e.g., "mouse", "click", "computer", "download") rather than creating native equivalents like French does.

### 9. QA CHECK PRIORITIES
*   🔍 **Accents:** "E" vs "È" (And vs Is) is a highly critical and common error.
*   🔍 **Formality Mix:** Ensure "tu" and "Lei" verb conjugations are not mixed within the same UI flow.

---

## Portuguese (Portugal vs. Brazil)
### Implementation Status: Implemented in ErrorSweep

### 1. GRAMMAR RULES
*   **Sentence structure:** Subject-Verb-Object (SVO).
*   **Pro-drop:** Subject pronouns are often omitted, more so in Portugal (PT-PT) than in Brazil (PT-BR).
*   **Gender:** Two genders (Masculine, Feminine).

### 2. PUNCTUATION RULES
*   **Quotation marks:** PT-PT uses angular quotes («...»). PT-BR heavily uses double quotes ("...").
*   **Space before/after:** Standard English spacing.

### 3. FORMATTING RULES
*   **Date format:** DD/MM/YYYY.
*   ⚠️ **Number formatting:** Period for thousands, comma for decimals in both regions (e.g., 1.000,50).
*   ⚠️ **Currency:** 
    *   Portugal: 10,00 € (Symbol after).
    *   Brazil: R$ 1.000,00 (Symbol before, with a space).

### 4. TYPOGRAPHY RULES
*   **Capitalization:** Sentence case for headings. Days and months are lowercase (e.g., segunda-feira, janeiro).

### 5. TRANSLATION RULES
*   ⚠️ **Formality levels & Regional variations:**
    *   **Portugal (PT-PT):** "Tu" (informal), "Você" (formal/respectful, though often omitted/implied via 3rd person verb to avoid sounding too direct).
    *   **Brazil (PT-BR):** "Você" is the standard pronoun for both informal and semi-formal address in most regions. "Tu" is used in specific regions (like the South) but usually with 3rd-person verb conjugations in colloquial speech. For UI, "Você" is the universal standard.
*   **Vocabulary:** "Ecrã" (PT) vs "Tela" (BR) for screen. "Ficheiro" (PT) vs "Arquivo" (BR) for file.

### 6. SUBTITLING RULES
*   **Maximum characters per line:** 38-42.
*   **Reading speed:** 15-18 CPS.

### 8. CULTURAL & LOCALIZATION NOTES
*   🌐 **Gerunds:** PT-BR heavily uses the gerund for continuous action (e.g., "estou fazendo"). PT-PT avoids it, using "a" + infinitive instead (e.g., "estou a fazer"). This is a massive tell-tale sign of bad localization targeting.

### 9. QA CHECK PRIORITIES
*   🔍 **Gerund vs Infinitive:** Flag gerunds in PT-PT target texts.
*   🔍 **Spelling Agreement:** Check for the 1990 Orthographic Agreement rules (Acordo Ortográfico), which removed silent consonants (e.g., "acção" -> "ação").

---

## Dutch
### Implementation Status: Implemented in ErrorSweep

### 1. GRAMMAR RULES
*   ⚠️ **Sentence structure:** SVO in main clauses, but V2 (verb-second) word order applies, meaning the finite verb is always the second element. In subordinate clauses, it is SOV (verbs move to the end).
*   **Gender:** Two grammatical genders: Common (de) and Neuter (het).
*   **Plurals:** Typically formed with -en or -s.

### 2. PUNCTUATION RULES
*   **Quotation marks:** Double quotes (" ") or single quotes (' ') are standard.
*   **Space before/after:** Standard English spacing.

### 3. FORMATTING RULES
*   **Date format:** DD-MM-YYYY or DD/MM/YYYY.
*   **Time format:** 24-hour clock separated by a colon or dot (e.g., 14:30 or 14.30).
*   ⚠️ **Number formatting:** Period or space for thousands, comma for decimals (e.g., 1.000,50).
*   **Currency:** € symbol before the amount (e.g., € 10,00).

### 4. TYPOGRAPHY RULES
*   **Capitalization:** Sentence case for headings. 
*   ⚠️ **Compound Words:** Like German, Dutch writes compound nouns as a single word (e.g., "gebruikersaccount" not "gebruikers account"). Splitting them is a grammar error called the "English disease" (Engelse ziekte).

### 5. TRANSLATION RULES
*   ⚠️ **Formality levels:** "Je/Jij" (informal) vs "U" (formal). Modern UI, SaaS, and B2C heavily default to "Je". B2B, finance, and legal default to "U".

### 6. SUBTITLING RULES
*   **Maximum characters per line:** 40.

### 9. QA CHECK PRIORITIES
*   🔍 **Compound Words:** Space inside a compound noun is a critical error (e.g., "wachtwoord herstel" -> must be "wachtwoordherstel").
*   🔍 **Formality Consistency:** Mixing "je" and "u" or their possessives ("jouw" / "uw") is a major failure.

---

## Polish
### Implementation Status: Implemented in ErrorSweep

### 1. GRAMMAR RULES
*   **Sentence structure:** SVO is the default, but highly flexible due to the case system.
*   ⚠️ **Cases:** Polish has 7 noun cases (Nominative, Genitive, Dative, Accusative, Instrumental, Locative, Vocative) which heavily alter word endings.
*   **Gender:** Three singular genders (Masculine, Feminine, Neuter) and two plural genders (Masculine personal, Non-masculine personal).
*   ⚠️ **No Articles:** Polish does not have definite (the) or indefinite (a/an) articles.

### 2. PUNCTUATION RULES
*   ⚠️ **Quotation marks:** Uses lower opening and upper closing quotes („...”).

### 3. FORMATTING RULES
*   **Date format:** DD.MM.YYYY (e.g., 31.12.2023).
*   ⚠️ **Number formatting:** Space for thousands, comma for decimals (e.g., 1 000,50).
*   **Currency:** The abbreviation "zł" (Złoty) is placed after the amount with a space (e.g., 10,00 zł).

### 4. TYPOGRAPHY RULES
*   **Capitalization:** Sentence case for headings. Days and months are lowercase.

### 5. TRANSLATION RULES
*   ⚠️ **Formality levels:** "Ty" (informal) vs "Pan/Pani" (formal Mr./Ms. used with 3rd-person verbs). UI software strongly prefers informal "Ty" or impersonal infinitives (e.g., "Zapisz" / Save) to avoid gendered/formal complexities.
*   **Placeholders:** Translating sentences with placeholders (e.g., "Created by {user}") is notoriously difficult due to cases. The translator must often rephrase to avoid forcing a variable into a specific case.

### 6. SUBTITLING RULES
*   **Maximum characters per line:** 40.

### 9. QA CHECK PRIORITIES
*   🔍 **Placeholder Context:** Check if placeholders naturally fit the grammatical case of the surrounding Polish sentence.
*   🔍 **Quotation Marks:** Standard double quotes ("") should be replaced with Polish quotes („”).

---

## Swedish, Norwegian, Danish (Nordic Languages)
### Implementation Status: Implemented in ErrorSweep

### 1. GRAMMAR RULES
*   ⚠️ **Sentence structure:** SVO in main clauses, but V2 (Verb-second) rule strictly applies (e.g., "Today *go* we" instead of "Today we go").
*   ⚠️ **Definite Articles:** Instead of a separate word for "the", the definite article is attached to the *end* of the noun (e.g., Swedish: "en bil" / a car -> "bilen" / the car).
*   **Passive voice:** Heavy use of s-passives (e.g., "ändras" / is changed).

### 2. PUNCTUATION RULES
*   **Quotation marks:** Swedish uses right-pointing double quotes for both opening and closing (”...”). Norwegian/Danish prefer guillemets pointing outward («...»).

### 3. FORMATTING RULES
*   **Date format:** YYYY-MM-DD or DD.MM.YYYY.
*   ⚠️ **Number formatting:** Space for thousands, comma for decimals (e.g., 1 000,50).

### 4. TYPOGRAPHY RULES
*   **Capitalization:** Sentence case.
*   ⚠️ **Compound Words:** Like German and Dutch, compound nouns must be written as a single word (e.g., "användarkonto" / user account). 

### 5. TRANSLATION RULES
*   ⚠️ **Formality:** Universally informal. The pronoun "du" is used almost exclusively in all contexts (B2B, B2C, UI, marketing). The formal "Ni" (Swedish) or "De" (Danish/Norwegian) is archaic and should be avoided unless specifically requested for highly formal legal text.

### 9. QA CHECK PRIORITIES
*   🔍 **Compound Nouns:** Särskrivning (writing compound words separately) is the most hated error in Nordic texts. 
*   🔍 **V2 Rule:** Ensure the verb is in the second position when sentences start with an adverb or time clause.

---

## Greek
### Implementation Status: Implemented in ErrorSweep

### 1. GRAMMAR RULES
*   **Sentence structure:** SVO, but highly flexible.
*   **Gender:** Three genders (Masculine, Feminine, Neuter).
*   **Cases:** Four cases (Nominative, Genitive, Accusative, Vocative).

### 2. PUNCTUATION RULES
*   ⚠️ **Question mark:** The Greek question mark is the English semicolon (;). The English question mark (?) is a major error.
*   ⚠️ **Quotation marks:** Guillemets («...»).

### 3. FORMATTING RULES
*   **Date format:** DD/MM/YYYY.
*   **Number formatting:** Period for thousands, comma for decimals (1.000,50).
*   **Currency:** € symbol after the amount.

### 4. TYPOGRAPHY RULES
*   **Script:** Greek alphabet.
*   ⚠️ **Capitalization and Accents:** In all-caps text, stress accents (τόνος) are entirely removed (e.g., "Ελληνικά" -> "ΕΛΛΗΝΙΚΑ").

### 5. TRANSLATION RULES
*   ⚠️ **Formality:** "Εσύ" (informal) vs "Εσείς" (formal/plural). SaaS often defaults to formal plural to ensure a professional tone.

### 9. QA CHECK PRIORITIES
*   🔍 **Question Mark:** Flag any `?` symbol in target text. It must be `;`.
*   🔍 **All-Caps Accents:** Ensure accents are stripped from all-uppercase headers.

---

## Russian
### Implementation Status: Implemented in ErrorSweep

### 1. GRAMMAR RULES
*   **Sentence structure:** SVO is standard, but the rich inflectional system allows almost any order for emphasis.
*   ⚠️ **Cases:** Six cases (Nominative, Genitive, Dative, Accusative, Instrumental, Prepositional). This severely impacts UI localization because nouns inside placeholders might need to change cases based on surrounding verbs/prepositions.
*   **Gender:** Three genders (Masculine, Feminine, Neuter).
*   ⚠️ **No Articles:** No words for "a", "an", or "the".

### 2. PUNCTUATION RULES
*   ⚠️ **Quotation marks:** Uses French-style guillemets («...») for primary quotes and lower/upper quotes („...“) for nested quotes.
*   **Dashes:** Em-dash (—) is heavily used to replace the verb "to be" in present tense (e.g., "Мой брат — врач" / My brother [is] a doctor).

### 3. FORMATTING RULES
*   **Date format:** DD.MM.YYYY.
*   **Time format:** 24-hour.
*   ⚠️ **Number formatting:** Space for thousands, comma for decimals (e.g., 1 000,50).
*   **Currency:** The abbreviation "₽" or "руб." follows the amount (e.g., 1 000 ₽).

### 4. TYPOGRAPHY RULES
*   **Script direction:** LTR. Cyrillic alphabet.
*   **Capitalization:** Sentence case is standard. Days and months are lowercase.

### 5. TRANSLATION RULES
*   ⚠️ **Formality levels:** "Ты" (informal) vs "Вы" (formal). In standard SaaS and UI, "Вы" is standard.
*   ⚠️ **Capitalizing "Вы":** In formal written correspondence addressing a specific single person, "Вы" (You) is capitalized. In general UI, websites, and manuals targeting a broad audience, "вы" is lowercase.

### 6. SUBTITLING RULES
*   **Maximum characters per line:** 38-40.

### 8. CULTURAL & LOCALIZATION NOTES
*   🌐 **Imperatives in UI:** Action buttons often use the infinitive (e.g., "Сохранить" / To save) or first-person plural, rather than direct imperative commands.

### 9. QA CHECK PRIORITIES
*   🔍 **Latin Confusables:** Cyrillic "С", "А", "О", "Е" look identical to Latin characters but have different Unicode values. QA must flag mixed scripts in words to prevent spoofing or search errors.
*   🔍 **Placeholder Case Agreements:** Variables injected into sentences (e.g., "{count} files") must account for complex Russian plural rules (1 file, 2-4 files, 5-0 files take different noun cases).

---

## Ukrainian
### Implementation Status: Implemented in ErrorSweep

### 1. GRAMMAR RULES
*   **Sentence structure:** Flexible SVO.
*   ⚠️ **Cases:** Seven cases (same six as Russian + Vocative case, which is heavily used when addressing the user directly).
*   **Gender:** Three genders.
*   **No Articles:** Like Russian, no definite/indefinite articles.

### 2. PUNCTUATION RULES
*   **Quotation marks:** Guillemets («...»).
*   **Apostrophe:** Ukrainian uses a specific, non-directional apostrophe (ʼ) rather than a smart quote.

### 3. FORMATTING RULES
*   **Date format:** DD.MM.YYYY.
*   **Number formatting:** Space for thousands, comma for decimals.
*   **Currency:** The symbol "₴" or abbreviation "грн" follows the amount (e.g., 100 ₴).

### 4. TYPOGRAPHY RULES
*   **Script:** Cyrillic alphabet, but includes specific letters not found in Russian (і, ї, ґ, є).

### 5. TRANSLATION RULES
*   ⚠️ **Formality:** "Ти" (informal) vs "Ви" (formal). SaaS UI defaults to "Ви".
*   ⚠️ **Vocative Case:** When greeting a user (e.g., "Hello, Ivan"), the name must change to the vocative case ("Привіт, Іване").

### 9. QA CHECK PRIORITIES
*   🔍 **Russianisms (Surzhyk):** Ensure pure Ukrainian vocabulary is used, avoiding Russian loanwords/calques unless strictly correct in Ukrainian.
*   🔍 **Apostrophe:** Check that the correct straight Ukrainian apostrophe (U+02BC) or standard straight quote (U+0027) is used, not curly English single quotes.

---

## Arabic (Modern Standard, Gulf, Egyptian)
### Implementation Status: Implemented in ErrorSweep

### 1. GRAMMAR RULES
*   **Sentence structure:** Traditionally Verb-Subject-Object (VSO), but Subject-Verb-Object (SVO) is increasingly common in modern digital contexts.
*   ⚠️ **Gender agreement:** Arabic has strict grammatical gender (Masculine, Feminine). Verbs, adjectives, and pronouns must agree with the subject.
*   ⚠️ **Dual form:** Arabic distinguishes between singular (1), dual (2), and plural (3+). Nouns and verbs change form when exactly two subjects are involved.
*   **Roots:** Highly inflected root system (typically 3 consonants) modified by vowel patterns and affixes.

### 2. PUNCTUATION RULES
*   ⚠️ **RTL Punctuation:** Uses the Arabic comma (،), Arabic semicolon (؛), and Arabic question mark (؟). Using English (,) or (?) is a strict error.
*   **Space before/after:** No space before punctuation; one space after.

### 3. FORMATTING RULES
*   **Date format:** DD/MM/YYYY.
*   ⚠️ **Number formatting:** Depending on the region/client, Arabic uses either Western Arabic numerals (1, 2, 3 - common in North Africa and modern UI) or Eastern Arabic numerals (١, ٢, ٣ - common in the Gulf and Egypt).
*   **Currency:** The symbol or abbreviation is typically placed *after* the amount (e.g., 100 ر.س).

### 4. TYPOGRAPHY RULES
*   ⚠️ **Script direction:** Strictly Right-to-Left (RTL).
*   ⚠️ **Cursive script:** Letters change shape depending on their position in a word (isolated, initial, medial, final). Letters must connect properly.
*   **Capitalization:** Arabic does not have uppercase or lowercase letters.

### 5. TRANSLATION RULES
*   ⚠️ **Dialects vs MSA:** Modern Standard Arabic (MSA) is the universal standard for SaaS UI, formal documents, and news. Dialects (Egyptian, Gulf, Levantine) should *only* be used for highly localized marketing, social media, or conversational chatbots.
*   **Formality levels:** "أنت" (Anta - you masculine) / "أنتِ" (Anti - you feminine) vs "أنتم" (Antum - plural). For SaaS UI, masculine plural is historically the default generic, though gender-neutral phrasing is preferred where possible.

### 6. SUBTITLING RULES
*   **Maximum characters per line:** 35-40 characters.
*   **Reading speed:** 15-18 CPS.

### 8. CULTURAL & LOCALIZATION NOTES
*   🌐 **Sensitivities:** Broad localization must strictly avoid references to gambling, alcohol, pork, or inappropriate imagery. 
*   🌐 **Religious phrasing:** Phrases like "Inshallah" (God willing) are deeply embedded in spoken dialects, but should generally be omitted in clinical tech UI translations unless transcribing verbatim.

### 9. QA CHECK PRIORITIES
*   🔍 **RTL Directionality:** Ensure numbers, English loan words, placeholders (e.g., `{{email}}`), and LTR brackets do not scramble the RTL layout. LRM/RLM (Left-to-Right / Right-to-Left Mark) insertion is often required.
*   🔍 **Punctuation:** Reject English commas (,) and question marks (?).

---

## Hebrew
### Implementation Status: Implemented in ErrorSweep

### 1. GRAMMAR RULES
*   **Sentence structure:** Subject-Verb-Object (SVO).
*   ⚠️ **Strict Gender:** Nouns, adjectives, verbs, and pronouns are heavily gendered (Masculine/Feminine) in both singular and plural.
*   **Definite Article:** The prefix "ה" (Ha-) is attached directly to the noun (e.g., "הספר" / the book).

### 2. PUNCTUATION RULES
*   **Punctuation marks:** Uses standard Western punctuation (., !?), but placed in an RTL context.
*   **Quotation marks:** Double quotes (" ") are standard.

### 3. FORMATTING RULES
*   **Date format:** DD.MM.YYYY.
*   **Number formatting:** Western digits (1, 2, 3). Comma for thousands, period for decimals.
*   **Currency:** The Shekel symbol (₪) is typically placed to the left of the number in RTL layout.

### 4. TYPOGRAPHY RULES
*   ⚠️ **Script direction:** Strictly Right-to-Left (RTL).
*   **Capitalization:** Hebrew does not have uppercase or lowercase letters.
*   **Acronyms:** Uses the geresh (׳) for single-letter abbreviations or gershayim (״) for multi-letter acronyms (e.g., ארה״ב for USA).

### 5. TRANSLATION RULES
*   ⚠️ **Gender-Neutral UI:** Because Hebrew is heavily gendered, translating "Welcome, user" forces a choice between masculine and feminine. Modern SaaS UI heavily uses the *infinitive form* (e.g., "לשמור" / To save) or plural inclusive forms to remain gender-neutral and avoid excluding female users.
*   **Loan words:** Heavy use of English tech transliterations (e.g., אינטרנט / Internet).

### 6. SUBTITLING RULES
*   **Maximum characters per line:** 35-40 characters.

### 8. CULTURAL & LOCALIZATION NOTES
*   🌐 **Work week:** The work week runs Sunday through Thursday. The weekend is Friday/Saturday. Localization involving scheduling/calendars must adapt to this.
*   🌐 **Religious Sensitivities:** Strict adherence to Kosher laws or Sabbath references may be required depending on the client.

### 9. QA CHECK PRIORITIES
*   🔍 **Gender-Neutral Verbs:** Ensure UI buttons and commands use the infinitive form to avoid gender bias.
*   🔍 **Bi-Di (Bidirectional) Text:** Validate the display order of English placeholders mixed with Hebrew text.

---

## Persian (Farsi)
### Implementation Status: Implemented in ErrorSweep

### 1. GRAMMAR RULES
*   ⚠️ **Sentence structure:** Subject-Object-Verb (SOV).
*   ⚠️ **No Gender:** Persian has absolutely no grammatical gender. The pronoun "او" (Ou) means both he and she.
*   **Plurals:** Typically formed with the suffixes "ـ‌ها" (-ha) or "ـان" (-an).

### 2. PUNCTUATION RULES
*   ⚠️ **RTL Punctuation:** Uses the Arabic comma (،) and Arabic question mark (؟).
*   **Space before/after:** No space before punctuation; one space after.

### 3. FORMATTING RULES
*   ⚠️ **Date format:** YYYY/MM/DD (Solar Hijri calendar is the official calendar in Iran, running offset from the Gregorian calendar).
*   ⚠️ **Number formatting:** Uses Extended Arabic-Indic numerals (۱, ۲, ۳, ۴, ۵, ۶, ۷, ۸, ۹, ۰). Note that 4, 5, and 6 are shaped differently than standard Arabic numerals.

### 4. TYPOGRAPHY RULES
*   ⚠️ **Script direction:** Right-to-Left (RTL).
*   ⚠️ **ZWNJ (Zero Width Non-Joiner):** Absolutely critical in Persian. Used to separate prefixes, suffixes, and compound words without breaking them into full spaces (e.g., "می‌رود" instead of "میرود" or "می رود").
*   **Capitalization:** None.

### 5. TRANSLATION RULES
*   ⚠️ **Formality levels:** "تو" (To - informal/intimate) vs "شما" (Shoma - formal/plural). SaaS and UI strictly use "شما".

### 8. CULTURAL & LOCALIZATION NOTES
*   🌐 **Ta'arof:** A complex system of extreme politeness in Iranian culture. While UI is more direct, business correspondence translation must elevate the politeness level significantly compared to English.

### 9. QA CHECK PRIORITIES
*   🔍 **ZWNJ Usage:** Missing ZWNJ is the most common and critical error in Persian digital text. Verify prefixes like "می" (Mi-) and plural suffixes "ها" (-ha) use ZWNJ.
*   🔍 **Numeral Shapes:** Ensure Persian numerals (۴, ۵, ۶) are used, not Arabic numerals (٤, ٥, ٦).

---

## Turkish
### Implementation Status: Implemented in ErrorSweep

### 1. GRAMMAR RULES
*   ⚠️ **Sentence structure:** Subject-Object-Verb (SOV).
*   ⚠️ **Agglutination:** Highly agglutinative. Suffixes are stacked onto base words to express case, possession, and tense (e.g., "Evlerinizden" / From your houses).
*   **No Gender:** Turkish has no grammatical gender. "O" means he, she, or it.

### 2. PUNCTUATION RULES
*   **Punctuation marks:** Standard English-like punctuation (., !?).
*   **Quotation marks:** Uses double quotes (" ").
*   **Apostrophe:** Used heavily to separate proper nouns from their grammatical suffixes (e.g., "Google'ın" / Google's).

### 3. FORMATTING RULES
*   **Date format:** DD.MM.YYYY.
*   ⚠️ **Number formatting:** Period for thousands, comma for decimals (1.000,50).
*   **Currency:** The Lira symbol (₺) is placed before the amount, or abbreviation (TL) placed after (e.g., ₺100 or 100 TL).

### 4. TYPOGRAPHY RULES
*   **Script direction:** Left-to-Right (LTR).
*   ⚠️ **Dotted and Dotless I:** Turkish features a critical orthographic distinction:
    *   Lowercase `i` capitalizes to `İ` (dotted).
    *   Lowercase `ı` (dotless) capitalizes to `I` (dotless).

### 5. TRANSLATION RULES
*   ⚠️ **Formality levels:** "Sen" (informal) vs "Siz" (formal/plural). SaaS UI defaults to "Siz".
*   **Passive voice:** Heavy use of passive voice for UI instructions (e.g., "Dosya yüklendi" / File was uploaded).

### 6. SUBTITLING RULES
*   **Maximum characters per line:** 40-42 characters.

### 9. QA CHECK PRIORITIES
*   🔍 **I/i Capitalization:** Using the English `I` for `İ` changes the word's meaning and is a strict spelling failure.
*   🔍 **Vowel Harmony:** Suffixes must match the vowels of the base word (e.g., "-dan" vs "-den"). Check suffix attachments on placeholders (e.g., `{company}'dan`).

---

## Swahili (Kiswahili)
### Implementation Status: Implemented in ErrorSweep

### 1. GRAMMAR RULES
*   **Sentence structure:** Subject-Verb-Object (SVO).
*   ⚠️ **Noun Classes:** Swahili does not use gender. Instead, it uses a complex system of noun classes (human, inanimate, abstract, etc.), marked by prefixes.
*   ⚠️ **Agglutinative Verbs:** Verbs are composed of a root with prefixes for subject, tense, object, and relatives (e.g., "Ninakupenda" / I-present-you-love).

### 2. PUNCTUATION RULES
*   **Punctuation marks:** Standard English punctuation.
*   **Quotation marks:** Double quotes (" ").

### 3. FORMATTING RULES
*   **Date format:** DD/MM/YYYY.
*   **Number formatting:** Comma for thousands, period for decimals.
*   **Time format:** ⚠️ **Swahili Time:** Culturally, time is measured from dawn and dusk rather than midnight/noon. 7:00 AM is "saa moja asubuhi" (the first hour of the morning). Tech UI usually defaults to standard 24-hour formats to avoid confusion, but conversational text must be handled carefully.

### 4. TYPOGRAPHY RULES
*   **Script direction:** Left-to-Right (LTR). Standard Latin alphabet.

### 5. TRANSLATION RULES
*   **Formality:** Swahili has minimal formal pronoun distinction. Standard UI uses direct address. Respect is conveyed through vocabulary (e.g., "Tafadhali" / Please).
*   **Tone:** Highly inclusive, pan-East-African tone is preferred over highly localized slang from Nairobi or Dar es Salaam.

### 9. QA CHECK PRIORITIES
*   🔍 **Concord/Agreement:** Ensure adjective and verb prefixes properly agree with the noun class prefix of the subject.
*   🔍 **Time Expressions:** Verify if the client requires Swahili cultural time or standard 24-hour time.

---

## Amharic
### Implementation Status: Implemented in ErrorSweep

### 1. GRAMMAR RULES
*   ⚠️ **Sentence structure:** Subject-Object-Verb (SOV).
*   **Gender:** Masculine and Feminine, which also applies to second-person pronouns (you-masculine, you-feminine).
*   **Verbs:** Highly complex, root-and-pattern system.

### 2. PUNCTUATION RULES
*   ⚠️ **Ge'ez Punctuation:** 
    *   Period / Full stop: `።` (Arat netib).
    *   Comma: `፣` (Netela seraz).
    *   Semicolon: `፤` (Drib seraz).
    *   Word separator (historical/archaic, often replaced by space in modern digital): `፡` (Hulet netib).

### 3. FORMATTING RULES
*   ⚠️ **Date format:** DD/MM/YYYY. Ethiopia uses its own solar calendar (7-8 years behind the Gregorian calendar). Client instructions must clarify whether to translate the date literally or convert it to the Ethiopian calendar.

### 4. TYPOGRAPHY RULES
*   ⚠️ **Script direction:** Left-to-Right (LTR).
*   ⚠️ **Script:** Written in the Ge'ez abugida (Fidel). Each character represents a consonant-vowel syllable.
*   **Capitalization:** None.

### 5. TRANSLATION RULES
*   ⚠️ **Formality levels:** "አንተ" (Anta - you masc.), "አንቺ" (Anchi - you fem.) vs "እርስዎ" (Erso - formal/respectful). Formal UI defaults to "እርስዎ" (Erso) to maintain respect and gender neutrality.

### 9. QA CHECK PRIORITIES
*   🔍 **Ge'ez Punctuation:** Ensure the English period (.) is completely replaced by `።`.
*   🔍 **Font Rendering:** Verify that the Ge'ez script renders correctly across the software stack.

---

## Yoruba
### Implementation Status: Implemented in ErrorSweep

### 1. GRAMMAR RULES
*   **Sentence structure:** Subject-Verb-Object (SVO).
*   **No Gender:** Grammatically genderless. "Ó" means he, she, or it.
*   ⚠️ **Tonal Language:** Yoruba relies heavily on tones (High, Mid, Low) to distinguish meaning.

### 2. PUNCTUATION RULES
*   **Punctuation marks:** Standard English punctuation.

### 3. FORMATTING RULES
*   **Date format:** DD/MM/YYYY.

### 4. TYPOGRAPHY RULES
*   **Script direction:** Left-to-Right (LTR).
*   ⚠️ **Diacritics:** Tone marks are written using acute (á) and grave (à) accents. Mid tone is left unmarked. Sub-dots (ẹ, ọ, ṣ) represent distinct vowels and consonants.

### 5. TRANSLATION RULES
*   ⚠️ **Formality/Respect:** The plural pronoun "Ẹ" or "Ẹyin" is strictly used as a singular honorific for elders or in formal business/UI contexts. Using the informal "O" is considered highly disrespectful in professional settings.

### 9. QA CHECK PRIORITIES
*   🔍 **Diacritic Integrity:** Missing sub-dots (e.g., writing "e" instead of "ẹ") or tone marks is a critical spelling and semantic failure.
*   🔍 **Honorific Pronouns:** Ensure the formal "Ẹ" is used for UI and business text.

---

## Hausa
### Implementation Status: Implemented in ErrorSweep

### 1. GRAMMAR RULES
*   **Sentence structure:** Subject-Verb-Object (SVO).
*   **Gender:** Masculine and Feminine.
*   ⚠️ **Tonal Language:** Hausa is tonal, but tones are rarely marked in standard written text.

### 2. PUNCTUATION RULES
*   **Punctuation marks:** Standard English punctuation.

### 3. FORMATTING RULES
*   **Date format:** DD/MM/YYYY.

### 4. TYPOGRAPHY RULES
*   **Script direction:** Left-to-Right (LTR) for the Latin-based *Boko* alphabet (standard for tech UI). Right-to-Left (RTL) for the Arabic-based *Ajami* alphabet (historical/religious).
*   ⚠️ **Hooked letters:** The Boko alphabet uses specific hooked consonants (ɓ, ɗ, ƙ, ƴ) and the letter (sh/ch) modifications.

### 5. TRANSLATION RULES
*   **Dialects:** Standard Hausa (Kano dialect) is preferred for media and software localization.

### 9. QA CHECK PRIORITIES
*   🔍 **Hooked Letters:** Missing hooked consonants (e.g., using "b" instead of "ɓ") is a severe spelling error.

---

## Zulu (isiZulu)
### Implementation Status: Implemented in ErrorSweep

### 1. GRAMMAR RULES
*   **Sentence structure:** Subject-Verb-Object (SVO).
*   ⚠️ **Agglutinative:** Zulu uses a complex system of prefixes and suffixes attached to a root word.
*   ⚠️ **Noun Classes:** Like Swahili, uses a noun class prefix system instead of grammatical gender.

### 2. PUNCTUATION RULES
*   **Punctuation marks:** Standard English punctuation.

### 3. FORMATTING RULES
*   **Date format:** DD/MM/YYYY or YYYY-MM-DD.

### 4. TYPOGRAPHY RULES
*   **Script direction:** Left-to-Right (LTR). Standard Latin alphabet.

### 5. TRANSLATION RULES
*   **Formality:** To show respect, the plural forms of pronouns are often used for a single person (e.g., "Nina"). 
*   **Consonants:** Zulu utilizes click consonants represented by `c` (dental), `q` (alveolar), and `x` (lateral).

### 9. QA CHECK PRIORITIES
*   🔍 **Prefix Agreement:** Concordial agreement between nouns, adjectives, and verbs is the most complex part of Zulu grammar and the most common failure point for machine translation.

---

## Afrikaans
### Implementation Status: Implemented in ErrorSweep

### 1. GRAMMAR RULES
*   **Sentence structure:** SVO in main clauses, SOV in subordinate clauses (similar to Dutch/German).
*   **No Gender:** Articles and adjectives are not gendered.
*   ⚠️ **Double Negative:** The defining feature of Afrikaans grammar. Sentences require a double "nie" (e.g., "Ek verstaan **nie** die reël **nie**" / I understand *not* the rule *not*).

### 2. PUNCTUATION RULES
*   **Punctuation marks:** Standard English punctuation.
*   **Quotation marks:** Double quotes (" ") or single quotes (' ').

### 3. FORMATTING RULES
*   **Date format:** YYYY-MM-DD or DD/MM/YYYY.
*   **Number formatting:** Space for thousands, comma for decimals.

### 4. TYPOGRAPHY RULES
*   **Script direction:** Left-to-Right (LTR).
*   **Accents:** Uses acute, grave, circumflex, and diaeresis diacritics (e.g., á, è, ê, ë).

### 5. TRANSLATION RULES
*   ⚠️ **Formality:** "Jy/Jou" (informal) vs "U" (formal). Business UI uses "U" or attempts impersonal phrasing.

### 9. QA CHECK PRIORITIES
*   🔍 **Double Negative:** Missing the final "nie" at the end of a negative sentence is a critical grammar error.

---

## Mandarin Chinese (Simplified)
### Implementation Status: Implemented in ErrorSweep

### 1. GRAMMAR RULES
*   **Sentence structure:** Subject-Verb-Object (SVO), though topic-prominent structures are very common.
*   ⚠️ **No Verb Conjugation:** Verbs do not change form for tense, person, or number. Tense/aspect is indicated by particles (e.g., 了, 过, 着) or time words.
*   ⚠️ **Classifiers/Measure Words:** Required when counting nouns (e.g., "一个人" / one [person-measure] person).
*   **No Plurals:** Nouns generally do not have plural forms, though "们" (men) is used for human pronouns (e.g., 我们 / we).

### 2. PUNCTUATION RULES
*   ⚠️ **Full-width Punctuation:** Uses full-width (double-byte) punctuation marks that take up the space of a full Chinese character (。，！？；：). Using ASCII punctuation (.,!?) is a strict error.
*   ⚠️ **Quotation marks:** Uses full-width double quotes (“ ”) and single quotes (‘ ’).
*   ⚠️ **Enumeration Comma:** A special teardrop comma (、) is used specifically to separate items in a list, rather than the standard comma (，).
*   **Space before/after:** NO spaces are used before or after Chinese punctuation.

### 3. FORMATTING RULES
*   ⚠️ **Date format:** YYYY年MM月DD日 (e.g., 2023年12月31日).
*   **Time format:** 24-hour clock or 12-hour with morning/afternoon designators (上午/下午).
*   ⚠️ **Number formatting:** Period for decimals, comma for thousands. However, large numbers are grouped by ten-thousands (万 - 10,000; 亿 - 100,000,000).
*   **Currency:** ¥ or CNY placed before the number (e.g., ¥100).

### 4. TYPOGRAPHY RULES
*   **Script direction:** Left-to-Right (LTR) for digital UI.
*   ⚠️ **No Word Spacing:** Chinese characters are written consecutively without spaces between words.
*   **Capitalization:** Not applicable.

### 5. TRANSLATION RULES
*   ⚠️ **Formality levels:** "你" (nǐ - familiar) vs "您" (nín - formal/respectful). Modern UI often uses "你" to be friendly, but B2B or legal text may require "您".
*   **Tone:** Passive voice should be avoided as it often implies a negative outcome in Chinese. Use active, direct phrasing for UI.

### 6. SUBTITLING RULES
*   ⚠️ **Maximum characters per line:** 14-16 characters (Chinese conveys much more meaning per character than Latin scripts).
*   **Reading speed:** 10-12 CPS.

### 7. TRANSCRIPTION RULES
*   **Filler words:** Use 嗯 (en) or 呃 (e).
*   **Numbers:** Typically spell out 1-10 (一，二); use digits for larger numbers.

### 8. CULTURAL & LOCALIZATION NOTES
*   🌐 **Target Audience:** Simplified Chinese (zh-CN) is the standard for mainland China and Singapore.
*   🌐 **Political Sensitivities:** Strict adherence to geographical naming conventions (e.g., references to Taiwan, Hong Kong, Macau) is required to avoid severe legal/business repercussions in mainland China.

### 9. QA CHECK PRIORITIES
*   🔍 **Punctuation Width:** Flag any ASCII punctuation (.,!?) inside Chinese text blocks.
*   🔍 **Spacing:** Flag any English/ASCII spaces inserted between Chinese characters.

---

## Mandarin Chinese (Traditional)
### Implementation Status: Implemented in ErrorSweep

### 1. GRAMMAR RULES
*   Identical to Simplified Chinese.

### 2. PUNCTUATION RULES
*   ⚠️ **Quotation marks (Taiwan):** Taiwan standard uses corner brackets (「 」 and 『 』) instead of double/single curly quotes.
*   **Full-width Punctuation:** Standard (。，！？).

### 3. FORMATTING RULES
*   ⚠️ **Date format:** YYYY/MM/DD or YYYY年MM月DD日. Note: Taiwan also uses the Minguo calendar (Gregorian year - 1911) for official documents, though tech UI uses Gregorian.
*   **Currency:** NT$ for Taiwan, HK$ for Hong Kong.

### 4. TYPOGRAPHY RULES
*   ⚠️ **Character Set:** Uses complex traditional strokes (e.g., 體 instead of 体).
*   **No Word Spacing:** Written continuously.

### 5. TRANSLATION RULES
*   ⚠️ **Regional Vocabulary:** Massive differences exist between Taiwan (zh-TW) and Hong Kong (zh-HK) terminology.
    *   Network: 網路 (TW) vs 網絡 (HK).
    *   Program: 程式 (TW) vs 程式 (HK).
    *   File: 檔案 (TW) vs 檔案 (HK) vs 文件 (CN).
    *   Quality assurance must strictly verify the target locale vocabulary.
*   **Formality:** "你" is overwhelmingly used; "您" is very rarely used in Taiwan UI.

### 6. SUBTITLING RULES
*   **Maximum characters per line:** 14-16 characters.

### 8. CULTURAL & LOCALIZATION NOTES
*   🌐 **Phonetic input:** Transliterations often rely on Bopomofo (Zhuyin) in Taiwan rather than Pinyin used in mainland China.

### 9. QA CHECK PRIORITIES
*   🔍 **Character Set Contamination:** The most critical QA check. A single Simplified character (e.g., 简) in a Traditional text payload is a severe failure.
*   🔍 **Quotation Marks:** Verify corner brackets (「 」) are used if the locale is zh-TW.

---

## Japanese
### Implementation Status: Implemented in ErrorSweep

### 1. GRAMMAR RULES
*   ⚠️ **Sentence structure:** Strictly Subject-Object-Verb (SOV). The verb MUST come at the end of the sentence.
*   ⚠️ **Particles:** Meaning is conveyed through postpositional particles (e.g., は wa, が ga, を o, に ni) that mark the grammatical function of the preceding noun.
*   **No Plurals or Gender:** Context defines number and gender.

### 2. PUNCTUATION RULES
*   ⚠️ **Full-width Punctuation:** Uses the ideographic comma (、) and ideographic full stop (。).
*   ⚠️ **Quotation marks:** Uses corner brackets (「 」) for primary quotes and double corner brackets (『 』) for nested quotes/titles.
*   **Question marks:** Traditionally, a question mark is not used; the particle か (ka) + full stop (。) indicates a question. However, full-width question marks (？) are widely used in modern UI/casual text.

### 3. FORMATTING RULES
*   **Date format:** YYYY年MM月DD日.
*   **Number formatting:** Comma for thousands, period for decimals. Like Chinese, grouped by ten-thousands (万, 億).
*   **Currency:** ¥ symbol before the amount.

### 4. TYPOGRAPHY RULES
*   ⚠️ **Scripts:** Uses a mix of three scripts simultaneously: Kanji (ideograms), Hiragana (native grammar/words), and Katakana (loan words/emphasis).
*   ⚠️ **No Word Spacing:** Written continuously. DO NOT insert spaces between words.

### 5. TRANSLATION RULES
*   ⚠️ **Formality (Keigo):** Deeply complex honorific system.
    *   *Teineigo* (Polite: Desu/Masu forms) - Standard for SaaS UI, manuals, and business text.
    *   *Sonkeigo* (Respectful) - Elevates the client/user. Used in customer service or luxury UI.
    *   *Kenjougo* (Humble) - Lowers the speaker.
*   **Pronouns:** "You" (あなた - anata) is often considered overly direct or rude. Sentences should be rephrased to omit the pronoun or use the user's title/name.
*   ⚠️ **Loanwords:** Heavy use of English tech terms transliterated into Katakana (e.g., "Download" -> ダウンロード). Note: Katakana words are often abbreviated uniquely (e.g., "Personal Computer" -> パソコン pasokon).

### 6. SUBTITLING RULES
*   **Maximum characters per line:** 13-15 characters.
*   **Reading speed:** 10-12 CPS.

### 8. CULTURAL & LOCALIZATION NOTES
*   🌐 **Apologies:** Japanese UI frequently apologizes for errors (e.g., "We are sorry, an error occurred"). Over-translating sterile English errors ("Error 404") without polite framing sounds blunt.

### 9. QA CHECK PRIORITIES
*   🔍 **Spacing:** English spaces left inside a Japanese string.
*   🔍 **Katakana Middle Dot:** Ensure the middle dot (・) is used to separate foreign names/words written in Katakana, not an English space.

---

## Korean
### Implementation Status: Implemented in ErrorSweep

### 1. GRAMMAR RULES
*   ⚠️ **Sentence structure:** Subject-Object-Verb (SOV).
*   ⚠️ **Agglutinative / Particles:** Uses postpositional particles (은/는, 이/가, 을/를) attached directly to nouns.
*   **No Gender:** No grammatical gender. Plurals exist (들) but are often omitted if context is clear.

### 2. PUNCTUATION RULES
*   **Punctuation marks:** Uses standard Western punctuation (., !?).
*   **Quotation marks:** Double quotes (" ") or single quotes (' ') are standard, though corner brackets are sometimes used in publishing.

### 3. FORMATTING RULES
*   **Date format:** YYYY년 MM월 DD일 (Space required before MM and DD). YYYY. MM. DD. is also common.
*   **Currency:** ₩ symbol before the amount.

### 4. TYPOGRAPHY RULES
*   ⚠️ **Spacing (Eojeol):** UNLIKE Chinese and Japanese, Korean strictly uses spaces between words/phrases (eojeols). A particle is attached to the noun with no space (e.g., "집에" = "house-to"), but separated from the next word by a space.
*   **Script:** Hangul. Each block is a syllable made of phonetic letters (jamo).

### 5. TRANSLATION RULES
*   ⚠️ **Formality (Honorifics):** Very strict hierarchy.
    *   *Haera-che* (Informal/Banmal): Used with friends/children.
    *   *Haeyo-che* (Polite/Yo-form): Conversational polite.
    *   *Hapsyo-che* (Formal/Deferential/Nida-form): Standard for B2B SaaS, broadcasting, and corporate UI (e.g., "저장합니다" / Save).
*   **Pronouns:** Like Japanese, direct use of "You" (당신) is rude in professional contexts. Omit the pronoun and use formal verb endings.

### 6. SUBTITLING RULES
*   **Maximum characters per line:** 14-16 characters.
*   **Reading speed:** 12-14 CPS.

### 9. QA CHECK PRIORITIES
*   🔍 **Particle Agreement:** Particles change based on whether the preceding noun ends in a vowel or consonant (e.g., 은 vs 는). Placeholders make this difficult (e.g., `{user}는`). Use the fallback combination particle `(은)는` when modifying variables.
*   🔍 **Honorific Consistency:** Mixing `-yo` forms and `-nida` forms in the same UI flow is a critical failure.

---

## Vietnamese
### Implementation Status: Implemented in ErrorSweep

### 1. GRAMMAR RULES
*   **Sentence structure:** Subject-Verb-Object (SVO).
*   ⚠️ **Analytic Language:** Words never change form. Tense, plurality, and grammatical roles are indicated by helper words (particles/classifiers) and word order.
*   **Adjective Placement:** Adjectives follow the noun (e.g., "áo đỏ" / shirt red).

### 2. PUNCTUATION RULES
*   **Punctuation marks:** Standard Western punctuation.
*   **Space before/after:** Standard English spacing.

### 3. FORMATTING RULES
*   **Date format:** DD/MM/YYYY. (e.g., ngày 31 tháng 12 năm 2023).
*   ⚠️ **Number formatting:** Period for thousands, comma for decimals (e.g., 1.000,50).
*   **Currency:** The abbreviation "VNĐ" or symbol "₫" goes after the amount, often with a space.

### 4. TYPOGRAPHY RULES
*   **Script:** Latin alphabet heavily modified with diacritics.
*   ⚠️ **Tonal Diacritics:** Vietnamese has 6 tones. Every vowel can take a tone mark, and some vowels take secondary shape diacritics (e.g., ệ, ắ).
*   **Capitalization:** Sentence case.

### 5. TRANSLATION RULES
*   ⚠️ **Pronouns:** Vietnamese lacks a generic "I/You". Pronouns are based on age, gender, and status relative to the speaker (anh, chị, em, chú, bác).
    *   **UI Standard:** Modern SaaS overwhelmingly uses "Bạn" (Friend/Peer) for "You" and "Tôi" (I/Me) for the system to remain neutral.
*   **Length:** Vietnamese translations expand significantly compared to English.

### 6. SUBTITLING RULES
*   **Maximum characters per line:** 38-40 characters.
*   **Reading speed:** 15-18 CPS.

### 9. QA CHECK PRIORITIES
*   🔍 **Pronoun Usage:** Flag any UI using familial pronouns (anh/chị) unless explicitly requested; enforce "Bạn".
*   🔍 **Font Rendering:** Verify stacked diacritics render correctly without clipping.

---

## Thai
### Implementation Status: Implemented in ErrorSweep

### 1. GRAMMAR RULES
*   **Sentence structure:** Subject-Verb-Object (SVO).
*   **Analytic:** No verb conjugation, no plurals, no gender.
*   **Adjectives:** Follow the noun.

### 2. PUNCTUATION RULES
*   ⚠️ **No Punctuation:** Traditional Thai does not use commas or periods. A space functions as a comma/period to indicate a pause or end of a sentence.
*   **Digital UI Exception:** Western punctuation (?, !, ") is sometimes used in modern digital/tech text, but it is not native.

### 3. FORMATTING RULES
*   ⚠️ **Date format:** DD/MM/YYYY. Often uses the Buddhist Era (BE) year, which is Gregorian + 543 years (e.g., 2023 is 2566 BE). Ensure client preference is clear.
*   **Number formatting:** Western digits (1,2,3) are standard in UI, though Thai numerals (๑, ๒, ๓) exist for formal/government use.

### 4. TYPOGRAPHY RULES
*   ⚠️ **No Word Spacing:** Words are written continuously without spaces. Spaces are only used at the end of clauses/sentences.
*   **Line breaking:** MUST be handled by a dictionary-aware line-breaking algorithm, as breaking in the middle of a word renders the text illegible.
*   **Capitalization:** None.

### 5. TRANSLATION RULES
*   ⚠️ **Politeness Particles:** Thai relies on gendered politeness particles at the end of sentences (ครับ 'krub' for male speakers, ค่ะ 'kha' for female speakers). UI software must omit these entirely to remain gender-neutral, relying on polite vocabulary instead.

### 6. SUBTITLING RULES
*   **Maximum characters per line:** 35-40 characters.
*   **Reading speed:** 15-18 CPS.

### 9. QA CHECK PRIORITIES
*   🔍 **Word Spacing:** Flag English-style spacing inserted between words.
*   🔍 **Gendered Particles:** Search for and flag ครับ/ค่ะ in UI strings.

---

## Indonesian (Bahasa Indonesia)
### Implementation Status: Implemented in ErrorSweep

### 1. GRAMMAR RULES
*   **Sentence structure:** Subject-Verb-Object (SVO).
*   ⚠️ **Affixation:** Heavily uses prefixes, suffixes, and circumfixes to change word class and meaning (e.g., *tulis* / write -> *penulis* / writer -> *menuliskan* / to write down).
*   **No Gender / Tense:** Verbs don't change for tense.
*   **Plurals:** Often formed by reduplication (e.g., *buku* / book -> *buku-buku* / books) if not implied by a number.

### 2. PUNCTUATION RULES
*   **Punctuation marks:** Standard English punctuation.
*   **Space before/after:** Standard English spacing.

### 3. FORMATTING RULES
*   **Date format:** DD/MM/YYYY.
*   ⚠️ **Number formatting:** Period for thousands, comma for decimals (e.g., 1.000,50).
*   **Currency:** "Rp" is placed directly before the amount with NO space (e.g., Rp1.000).

### 4. TYPOGRAPHY RULES
*   **Script:** Standard Latin alphabet. No diacritics natively required.
*   **Capitalization:** Title Case is very common for buttons and menus (e.g., "Simpan Perubahan" / Save Changes).

### 5. TRANSLATION RULES
*   ⚠️ **Formality:** "Kamu" (informal) vs "Anda" (formal). B2B and SaaS software strictly uses "Anda" (which is always capitalized). Modern B2C apps might use "Kamu".
*   **Passive Voice:** Highly natural and frequently used in UI instructions (e.g., "File berhasil diunggah" / File was successfully uploaded).

### 6. SUBTITLING RULES
*   **Maximum characters per line:** 38-40 characters.
*   **Reading speed:** 15-18 CPS.

### 9. QA CHECK PRIORITIES
*   🔍 **Capitalization of 'Anda':** If "Anda" is used, it must be capitalized even in the middle of a sentence.
*   🔍 **Currency Spacing:** Flag spaces between Rp and the number.

---

## Malay (Bahasa Melayu)
### Implementation Status: Implemented in ErrorSweep

### 1. GRAMMAR RULES
*   **Sentence structure:** SVO. Highly mutually intelligible with Indonesian, sharing the same base grammar and affixation rules.

### 2. PUNCTUATION RULES
*   **Punctuation marks:** Standard English punctuation.

### 3. FORMATTING RULES
*   **Date format:** DD/MM/YYYY.
*   ⚠️ **Number formatting:** UNLIKE Indonesian, Malay uses the English system: Comma for thousands, period for decimals (1,000.50).
*   **Currency:** "RM" before the amount with no space (e.g., RM100).

### 5. TRANSLATION RULES
*   ⚠️ **False Friends vs Indonesian:** Tech vocabulary diverges significantly between Malaysia (ms-MY) and Indonesia (id-ID).
    *   Download: Muat turun (MS) vs Unduh (ID)
    *   Upload: Muat naik (MS) vs Unggah (ID)
    *   Password: Kata laluan (MS) vs Kata sandi (ID)
*   **Formality:** "Awak" (informal) vs "Anda" (formal). SaaS uses "Anda".

### 9. QA CHECK PRIORITIES
*   🔍 **Indonesian Contamination:** The most critical QA check for Malay. Flag any Indonesian-specific tech terms (Unduh, Unggah, Sandi) in a Malay target file.
*   🔍 **Number Formatting:** Ensure commas are used for thousands, not periods.

---

## Tagalog / Filipino
### Implementation Status: Implemented in ErrorSweep

### 1. GRAMMAR RULES
*   ⚠️ **Sentence structure:** Verb-Subject-Object (VSO) is the native structure, though SVO is common due to English influence.
*   ⚠️ **Focus System:** Austronesian alignment system where the verb affix changes based on whether the focus of the sentence is the actor, object, location, or beneficiary.
*   **No Gender:** The pronoun "siya" means both he and she.

### 2. PUNCTUATION RULES
*   **Punctuation marks:** Standard English punctuation.

### 3. FORMATTING RULES
*   **Date format:** MM/DD/YYYY (US influence) or DD/MM/YYYY. Check client preference.
*   **Number formatting:** Comma for thousands, period for decimals.
*   **Currency:** ₱ (Peso) symbol before the number.

### 4. TYPOGRAPHY RULES
*   **Script:** Latin alphabet.
*   **Capitalization:** Sentence case.

### 5. TRANSLATION RULES
*   ⚠️ **Politeness markers:** "Po" and "Opo" are used to show respect to elders or superiors. While acceptable in conversational text, SaaS UI often omits them to remain clean, though they may appear in customer support templates.
*   ⚠️ **Taglish (Code-switching):** Heavy use of English loanwords. Translating complex tech terms into deep/pure Tagalog (e.g., translating "Website" to "Pook-sapot") makes the UI sound archaic and unnatural. Use English terms natively (e.g., "I-click ang button").

### 6. SUBTITLING RULES
*   **Maximum characters per line:** 38-40 characters. Words are long due to affixation.

### 9. QA CHECK PRIORITIES
*   🔍 **Over-localization:** Flag archaic pure-Tagalog terms where standard Taglish/English loanwords are expected in modern UI.

---

## Burmese (Myanmar)
### Implementation Status: Implemented in ErrorSweep

### 1. GRAMMAR RULES
*   ⚠️ **Sentence structure:** Subject-Object-Verb (SOV).
*   **Analytic:** Meaning is modified by postpositional particles.

### 2. PUNCTUATION RULES
*   ⚠️ **Punctuation:** Uses native punctuation marks. `၊` (Pud-mya) acts as a comma. `။` (Pud-ma) acts as a full stop.

### 3. FORMATTING RULES
*   **Date format:** DD/MM/YYYY.
*   ⚠️ **Number formatting:** Usually uses Myanmar numerals (၀, ၁, ၂, ၃, ٤, ၅, ၆, ٧, ٨, ٩), though Western digits are appearing in modern tech UI.

### 4. TYPOGRAPHY RULES
*   **Script direction:** Left-to-Right (LTR).
*   ⚠️ **No Word Spacing:** Words are written continuously. Spaces are used to separate phrases or clauses, similar to commas in English.
*   ⚠️ **Font Standards:** Unicode is the global standard, but legacy systems used the non-Unicode "Zawgyi" font. Ensure pure Unicode (e.g., Pyidaungsu, Noto Sans Myanmar) is used and Zawgyi text is converted.

### 5. TRANSLATION RULES
*   **Formality:** High distinction between written/formal (literary) and spoken (colloquial) registers. SaaS/UI usually uses a polite conversational or simplified formal register.

### 6. SUBTITLING RULES
*   **Maximum characters per line:** 35-40 characters.

### 9. QA CHECK PRIORITIES
*   🔍 **Zawgyi Contamination:** Run encoding checks to ensure text is Unicode compliant, not Zawgyi encoded.
*   🔍 **Punctuation:** Ensure `။` is used instead of the English period.

---

## Khmer (Cambodian)
### Implementation Status: Implemented in ErrorSweep

### 1. GRAMMAR RULES
*   **Sentence structure:** Subject-Verb-Object (SVO).
*   **Analytic:** No conjugation or inflection. Uses helper words for tense and plurality.
*   **Adjectives:** Follow the noun.

### 2. PUNCTUATION RULES
*   ⚠️ **Punctuation:** `។` (Khan) is used for a full stop. Spaces are used for pauses (commas).

### 3. FORMATTING RULES
*   **Date format:** DD/MM/YYYY.
*   ⚠️ **Number formatting:** Khmer numerals (០, ១, ២, ៣, ៤, ៥, ៦, ៧, ៨, ៩) are standard, though Western digits are common in UI.
*   **Currency:** KHR symbol (៛) after the amount.

### 4. TYPOGRAPHY RULES
*   **Script direction:** Left-to-Right (LTR).
*   ⚠️ **No Word Spacing:** Written continuously without spaces between words. Spaces separate clauses/sentences.
*   **Zero Width Space (ZWSP):** Often inserted manually or via engine between words to help browsers line-break properly, as Khmer line-breaking algorithms are historically unreliable.

### 5. TRANSLATION RULES
*   **Formality:** High reliance on royal and monk vocabulary in specific domains, but standard tech UI uses polite common vocabulary.

### 9. QA CHECK PRIORITIES
*   🔍 **Khan Usage:** Verify `។` is used instead of `.`.
*   🔍 **Line Breaking (ZWSP):** Ensure long continuous strings do not break UI layouts if ZWSP is missing.

---

## Lao
### Implementation Status: Implemented in ErrorSweep

### 1. GRAMMAR RULES
*   **Sentence structure:** Subject-Verb-Object (SVO).
*   **Analytic:** Closely related to Thai. No verb conjugation, plurals, or gender.

### 2. PUNCTUATION RULES
*   ⚠️ **Punctuation:** Like Thai, spaces function as commas/periods. Western punctuation (?, !, ") is increasingly used in modern UI.

### 3. FORMATTING RULES
*   **Date format:** DD/MM/YYYY.
*   **Number formatting:** Western digits or Lao numerals (໐, ໑, ໒, ໓, ໔, ໕, ໖, ໗, ໘, ໙).
*   **Currency:** Kip symbol (₭).

### 4. TYPOGRAPHY RULES
*   **Script direction:** Left-to-Right (LTR).
*   ⚠️ **No Word Spacing:** Written continuously.

### 5. TRANSLATION RULES
*   **Vocabulary:** Do not use Thai vocabulary, even though the languages are mutually intelligible in spoken form. Lao has distinct orthography and lexical preferences.

### 9. QA CHECK PRIORITIES
*   🔍 **Thai Contamination:** Flag Thai characters or obvious Thai loanwords where native Lao equivalents exist.

---

## Sinhala
### Implementation Status: Implemented in ErrorSweep

### 1. GRAMMAR RULES
*   ⚠️ **Sentence structure:** Subject-Object-Verb (SOV).
*   **Inflection:** Highly inflected verbs and nouns. Two main verb classes (volitive and involitive).
*   **Diglossia:** Massive difference between spoken and written grammar.

### 2. PUNCTUATION RULES
*   **Punctuation marks:** Uses standard English punctuation (., !?).

### 3. FORMATTING RULES
*   **Date format:** DD/MM/YYYY.
*   **Number formatting:** Comma for thousands, period for decimals.
*   **Currency:** Rs or රු. before the amount.

### 4. TYPOGRAPHY RULES
*   **Script direction:** Left-to-Right (LTR).
*   **Spacing:** Standard spaces between words.

### 5. TRANSLATION RULES
*   ⚠️ **Diglossia/Register:** Tech UI must bridge the gap between formal literary Sinhala (which sounds overly academic) and spoken Sinhala (which looks unprofessional). A "simplified formal" register is standard for software.

### 9. QA CHECK PRIORITIES
*   🔍 **Font Rendering:** Verify complex vowel diacritics render correctly without separating from the base consonant.

---

## Mongolian
### Implementation Status: Implemented in ErrorSweep

### 1. GRAMMAR RULES
*   ⚠️ **Sentence structure:** Subject-Object-Verb (SOV).
*   **Agglutinative:** Uses suffixes for case, number, and tense.
*   ⚠️ **Vowel Harmony:** Suffixes must harmonize with the root word's vowels (front vs back vowels).

### 2. PUNCTUATION RULES
*   **Punctuation marks:** Standard Western/Cyrillic punctuation (., !?).
*   **Quotation marks:** Guillemets («...»).

### 3. FORMATTING RULES
*   **Date format:** YYYY-MM-DD or DD.MM.YYYY.
*   **Currency:** Tugrik symbol (₮).

### 4. TYPOGRAPHY RULES
*   **Script direction:** Left-to-Right (LTR) for Mongolian Cyrillic (the standard in modern Mongolia and all software UI). Vertical/Top-to-Bottom for traditional Mongolian script (Inner Mongolia/historical).
*   **Spacing:** Standard spaces between words.

### 5. TRANSLATION RULES
*   **Formality:** "Та" (Formal/Plural you) vs "Чи" (Informal singular you). UI uses "Та".

### 9. QA CHECK PRIORITIES
*   🔍 **Vowel Harmony:** Suffixes applied to English placeholders (e.g., `{user}-д`) must be checked carefully by reviewers, as the system cannot automatically harmonize them without knowing the variable.
