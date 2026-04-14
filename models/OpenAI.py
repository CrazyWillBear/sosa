from langchain_openai import ChatOpenAI


gpt_5_mini  = ChatOpenAI(model="gpt-5-mini",    temperature=0.3,    reasoning_effort="minimal")
gpt_5       = ChatOpenAI(model="gpt-5",         temperature=0.3,    reasoning_effort="minimal")
gpt_5_4     = ChatOpenAI(model="gpt-5.4",       temperature=0.3,    reasoning_effort="minimal")
gpt_4o      = ChatOpenAI(model="gpt-4o",        temperature=0.3,    reasoning_effort="minimal")
