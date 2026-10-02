# DeepEval Synthetic Goldens API (Level_1)

FastAPI backend service to generate evaluation datasets (Goldens) from custom documents (`.md`, `.db`, `.txt`, `.pdf`, `.sql`, `.csv`, `.json`) using **DeepEval**, **Qwen 2.5 (7B)**, and **Nomic Embeddings** via local **Ollama**.

---

## Running the Server

In Fish shell:
```fish
cd /home/rushikesh/Selvin/Level_1
source myenv/bin/activate.fish
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Or run directly:
```bash
./main.py
```

- **Base URL**: `http://localhost:8000`
- **Interactive Swagger Docs**: `http://localhost:8000/docs`

---

## API Specification for Frontend UI

### Single Endpoint: `POST /api/generate-goldens`

Send documents (files or direct text) and the number of goldens to generate.

#### Request (`multipart/form-data`):
| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `num_goldens` | `integer` | No (default: `5`) | Number of goldens to generate per context |
| `files` | `List[UploadFile]` | Optional* | Document files (`.md`, `.db`, `.txt`, `.pdf`, etc.) |
| `document_text` | `string` | Optional* | Direct text/markdown (leave empty if uploading files) |

*\*Note: Provide either `files` or `document_text`.*

#### Example Frontend Fetch Call:
```javascript
const formData = new FormData();
formData.append("num_goldens", 5);

// If uploading files:
fileList.forEach(file => formData.append("files", file));

// Or if sending text instead:
// formData.append("document_text", "Policy text...");

const response = await fetch("http://localhost:8000/api/generate-goldens", {
  method: "POST",
  body: formData
});

const data = await response.json();
console.log("Total generated:", data.total_generated);
console.log("Top 5 Goldens to display:", data.first_5_goldens);
```

---

### Response JSON (Formatted for UI Display)

```json
{
  "status": "success",
  "total_generated": 10,
  "requested_count": 10,
  "execution_time_seconds": 85.3,
  "first_5_goldens": [
    {
      "id": "None",
      "input": "What are the specific conditions and duration for returning electronic items?",
      "expected_output": "The return policy for electronic items allows returns within 15 days.",
      "context": [
        "Electronic Item has return policy of 15 days.\nClothing has a return policy of 4 days."
      ],
      "evolutions": ["Constrained"],
      "synthetic_input_quality": 1.0,
      "context_quality": 0.875,
      "source_file": "policy.md"
    }
  ],
  "files_processed": ["policy.md"]
}
```

#### Fields for the UI:
- **`first_5_goldens`**: Directly iterate over this array in your frontend component to display the top 5 questions, expected answers, contexts, evolutions, and quality scores.
- **`total_generated`**: Total count of goldens generated.
- **`execution_time_seconds`**: Elapsed time in seconds.
