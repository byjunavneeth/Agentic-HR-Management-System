"""Screens a question before it reaches the pipeline.

Returns None when the question should go on to the HR pipeline, otherwise a dict with a custom
reply: {"blocked": True, "kind": "unauthorized" | "offtopic" | "greeting", "category", "title",
"message", "suggestions"}.  Rule based on purpose, so it costs no LLM call and cannot be talked round.
"""
import re

SUGGESTIONS = [
    "How many active employees does each department have?",
    "Which projects use Python and who works on them?",
    "What does the leave policy say about paternity leave?",
]

_I = re.IGNORECASE
_DATA = r"(employees?|staff|records?|tables?|rows?|salar(?:y|ies)|payroll|database|data|entries|entry|profiles?|attendance|reviews?|candidates?|departments?|projects?|skills?|everything|all)"

UNAUTH = [
    ("write", re.compile(r"^\W*(?:please\s+|pls\s+|can you\s+|could you\s+|just\s+)*(?:delete|drop|truncate|erase|wipe|insert|overwrite|alter|destroy)\b.{0,60}?\b" + _DATA, _I | re.S)),
    ("write", re.compile(r"^\W*(?:please\s+|pls\s+|can you\s+|could you\s+|just\s+)*(?:update|change|edit|modify|set|raise|increase|reduce|decrease|give|promote|fire|terminate|approve|reject)\b.{0,80}?(?:\b(?:to|by|=)\s*[\d₹$%]|\ball (?:the )?(?:employees|staff)|\beveryone)", _I | re.S)),
    ("write", re.compile(r"\b(?:drop|truncate|delete\s+from|insert\s+into|update\s+\w+\s+set|alter\s+table)\b", _I)),
    ("secrets", re.compile(r"\b(?:passwords?|passcodes?|api[\s_-]?keys?|secret keys?|access tokens?|auth tokens?|connection strings?|credentials?|private keys?|\.env|database url|db url|groq key|neo4j (?:password|uri))\b", _I)),
    ("injection", re.compile(r"\b(?:ignore|disregard|forget|override)\b.{0,30}\b(?:previous|prior|above|all|your|these)\b.{0,30}\b(?:instructions?|rules?|prompts?|guidelines?|restrictions?)\b|\b(?:system prompt|developer mode|jailbreak|dan mode|act as (?:an? )?(?:unrestricted|root|admin))\b|reveal (?:your|the) (?:prompt|instructions)", _I | re.S)),
    ("bypass", re.compile(r"\b(?:bypass|circumvent|disable|turn off|get around|hack(?:ing)? into|break into)\b.{0,30}\b(?:security|login|authentication|access|permissions?|guard|filter|restrictions?|limit)\b|\b(?:admin|root|superuser) access\b|\bsudo\b|\bprivilege escalation\b", _I | re.S)),
    ("sensitive", re.compile(r"\b(?:aadhaar|aadhar|passport number|pan card number|bank account (?:number|details)|credit card|debit card|cvv|ifsc|home address|residential address|personal (?:phone|mobile|email)|medical records?|health records?)\b", _I)),
]

HR = re.compile(r"\b(?:employees?|employed|staff|workforce|headcount|team|teams|department|departments|dept|salar(?:y|ies)|pay|paid|payroll|payslip|bonus|ctc|compensation|leave|leaves|vacation|holiday|attendance|absent|present|late|overtime|project|projects|client|clients|vendor|skill|skills|training|trainings|course|certification|candidate|candidates|resume|resumes|cv|interview|hiring|hire|hired|recruit\w*|applicant|review|reviews|appraisal|performance|rating|promotion|promoted|promote|manager|managers|lead|leads|report(?:s|ing)?|designation|role|roles|joined|joining|resign\w*|attrition|notice period|experience|policy|policies|benefit|benefits|insurance|maternity|paternity|probation|onboarding|mentor\w*|risk|risks|deadline|knowledge graph|graph|document|documents|sql|database|hr|human resources|nexora)\b", _I)

OFFTOPIC = [
    ("everyday", re.compile(r"\b(?:weather|temperature outside|forecast|rain(?:ing)? today|recipe|cook|restaurant|pizza|biryani|movie|film|song|lyrics|music|album|netflix|cricket|ipl|football|match score|world cup|olympics|horoscope|astrology|travel tips|flight|hotel|vacation spots)\b", _I)),
    ("general", re.compile(r"\b(?:capital of|prime minister|president of|who (?:invented|discovered|wrote|painted)|history of|meaning of life|how tall is|how far is|population of|speed of light|largest (?:country|ocean|planet))\b", _I)),
    ("finance", re.compile(r"\b(?:bitcoin|crypto(?:currency)?|ethereum|stock price|share price|nifty|sensex|nasdaq|forex|exchange rate|mutual fund|gold rate|petrol price)\b", _I)),
    ("creative", re.compile(r"\b(?:tell me a joke|joke|riddle|poem|story|essay|limerick|rap|write (?:a|an|me) (?:song|poem|story|essay|code|program|script)|translate|solve (?:this|the)? ?(?:equation|puzzle)|what is \d+\s*[-+*/x]\s*\d+|calculate \d)\b", _I)),
    ("tech", re.compile(r"\b(?:write (?:a )?(?:python|java|javascript|c\+\+|html|css|sql)\b|debug my|fix my code|leetcode|how do i (?:install|code|program)|explain (?:python|java|react|docker|kubernetes)|chatgpt|openai|gemini|who are you|what are you|which model|what model|are you (?:chatgpt|gpt|claude|an ai)|your (?:name|creator|developer))\b", _I)),
]
GREETING = re.compile(r"^\W*(?:hi+|hello+|hey+|hola|namaste|good (?:morning|afternoon|evening)|yo|sup|thanks?(?: you)?|thank you|ok(?:ay)?|cool|nice|great|bye|goodbye|help|what can you do\??)\W*$", _I)

REPLIES = {
    "write": ("Request not permitted",
              "This assistant is read-only, so it cannot create, change or delete anything. Salaries, records and documents can only be changed through the HR system by someone with the right access. I can tell you what the data currently says instead."),
    "secrets": ("Request not permitted",
                "Passwords, keys, connection strings and other credentials are never shared through this assistant, and I do not have a way to show them. If you need access to a system, please ask your administrator."),
    "injection": ("Request not permitted",
                  "I cannot change or reveal how I am set up, and I will keep following the rules I was given. If you have a genuine HR question, ask it directly and I will answer from the data."),
    "bypass": ("Request not permitted",
               "I cannot help with getting around logins, permissions or other safeguards. Access to HR data is controlled on purpose. Please contact your administrator if you need more access."),
    "sensitive": ("Request not permitted",
                  "That kind of personal or sensitive detail is not something this assistant provides. I can help with work-related information such as roles, projects, skills, attendance summaries and policies."),
    "everyday": ("Outside what I can help with",
                 "That is outside my area. I only answer questions about this company's people, projects, pay, attendance, training and HR policies. Try one of these instead."),
    "general": ("Outside what I can help with",
               "I am built for HR questions about this organisation and do not answer general knowledge questions. Here are some things I can help with."),
    "finance": ("Outside what I can help with",
                "Market prices and personal finance are outside my scope. I can answer questions about payroll, salaries and compensation inside the company data."),
    "creative": ("Outside what I can help with",
                "I do not write jokes, stories, code or do general calculations. I can look things up in the HR database, the knowledge graph and the HR documents."),
    "tech": ("Outside what I can help with",
             "I am the HR Intelligence assistant for this project, and I only answer questions about the HR data. Here are some good places to start."),
    "unknown": ("Outside what I can help with",
                "I could not connect that to the HR data I have. Try asking about employees, departments, projects, skills, pay, attendance, training or policies."),
}


def check(question):
    q = (question or "").strip()
    for cat, rx in UNAUTH:
        if rx.search(q):
            t, m = REPLIES[cat]
            return {"blocked": True, "kind": "unauthorized", "category": cat, "title": t, "message": m, "suggestions": SUGGESTIONS[:2]}
    if GREETING.match(q):
        return {"blocked": True, "kind": "greeting", "category": "greeting", "title": "Hello",
                "message": "Hello. I can answer questions about employees, departments, projects, skills, pay, attendance, training and HR policies, and I show where every fact came from. What would you like to know?",
                "suggestions": SUGGESTIONS}
    if not HR.search(q):
        for cat, rx in OFFTOPIC:
            if rx.search(q):
                t, m = REPLIES[cat]
                return {"blocked": True, "kind": "offtopic", "category": cat, "title": t, "message": m, "suggestions": SUGGESTIONS}
    return None
