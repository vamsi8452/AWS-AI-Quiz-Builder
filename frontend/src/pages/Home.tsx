import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Card } from "../components/Card";
import { Button } from "../components/Button";
import {
  createStudySetFromText,
  createStudySetFromUpload,
  getPresignedUpload,
} from "../api/client";

export default function Home() {
  const nav = useNavigate();
  const [text, setText] = useState("");
  const [mode, setMode] = useState<"paste" | "upload">("paste");
  const [file, setFile] = useState<File | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onCreate() {
    setError(null);
    if (mode === "paste") {
      if (!text.trim()) {
        setError("Paste some text to summarize.");
        return;
      }
    } else if (!file) {
      setError("Choose a file to upload.");
      return;
    }

    try {
      setIsCreating(true);
      const selectedFile = file;
      const created =
        mode === "paste"
          ? await createStudySetFromText(text)
          : await (async () => {
              if (!selectedFile) {
                throw new Error("Missing upload file.");
              }
              const { url, key } = await getPresignedUpload(
                selectedFile.name,
                selectedFile.type || "text/plain"
              );
              if (!url || !key) {
                throw new Error("File upload is only available when connected to the backend API.");
              }
              const uploadRes = await fetch(url, {
                method: "PUT",
                headers: {
                  "content-type": selectedFile.type || "text/plain",
                },
                body: selectedFile,
              });
              if (!uploadRes.ok) {
                throw new Error("Failed to upload file.");
              }
              return createStudySetFromUpload(key);
            })();
      nav(`/study-sets/${created.id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to create quiz.");
    } finally {
      setIsCreating(false);
    }
  }

  return (
    <div className="mx-auto grid max-w-3xl gap-6 min-h-screen place-content-center">
      <div className="grid gap-2">
        <h1 className="text-2xl font-semibold">AI Quiz Builder</h1>
        <p className="text-sm text-gray-600">
          Upload a file or paste text to generate a quiz.
        </p>
      </div>

      <Card>
        <div className="grid gap-4">
          <div className="flex flex-wrap gap-2">
            <Button
              variant={mode === "paste" ? "primary" : "secondary"}
              onClick={() => setMode("paste")}
              disabled={isCreating}
            >
              Paste text
            </Button>
            <Button
              variant={mode === "upload" ? "primary" : "secondary"}
              onClick={() => setMode("upload")}
              disabled={isCreating}
            >
              Upload file
            </Button>
          </div>

          {mode === "paste" ? (
            <div>
              <textarea
                value={text}
                onChange={(e) => setText(e.target.value)}
                placeholder="Paste your notes here..."
                rows={6}
                aria-label="Paste text"
                className="w-full border border-gray-200 bg-white px-3 py-2 text-sm focus:border-black focus:outline-none"
              />
            </div>
          ) : (
            <div className="grid gap-2">
              <input
                type="file"
                accept=".txt,.pdf"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                className="w-full border border-gray-200 bg-white px-3 py-2 text-sm focus:border-black focus:outline-none"
              />
              {file ? (
                <p className="text-xs text-gray-600">Selected: {file.name}</p>
              ) : (
                <p className="text-xs text-gray-600">
                  Choose a file to summarize.
                </p>
              )}
            </div>
          )}

          {error && <p className="text-sm text-red-600">{error}</p>}

          <div className="flex flex-wrap gap-2">
            <Button onClick={onCreate} isLoading={isCreating}>
              Generate quiz
            </Button>
            <Button
              variant="secondary"
              onClick={() => {
                setText("");
                setFile(null);
                setError(null);
              }}
              disabled={isCreating}
            >
              Clear
            </Button>
          </div>
        </div>
      </Card>
    </div>
  );
}
