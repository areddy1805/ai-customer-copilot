# Failure Modes

## 1. planning_failure

**Definition**
System selects wrong tool or fails to select any tool.

**Cause**
- incorrect intent classification
- decomposition errors
- missing rule overrides

**Detection**
- actual_tool != expected_tool
- actual_tool = []

**Mitigation**
- strengthen rules (fast-path)
- improve classifier
- enforce fallback paths

---

## 2. retrieval_failure

**Definition**
RAG returns incorrect or irrelevant information.

**Cause**
- poor embeddings
- weak retrieval
- missing documents

**Detection**
- tool_used = rag
- keyword_match = 0

**Mitigation**
- improve embeddings
- reranking
- better chunking

---

## 3. tool_failure

**Definition**
Tool executes but fails or returns error.

**Cause**
- invalid inputs
- downstream failure
- business rule rejection

**Detection**
- metrics.error present
- tool response status = failed

**Mitigation**
- input validation
- retries
- fallback handling

---

## 4. unknown

**Definition**
Failure not classified by system.

**Cause**
- unhandled edge cases
- unexpected exceptions

**Detection**
- failure_type = unknown

**Mitigation**
- extend taxonomy
- add logging