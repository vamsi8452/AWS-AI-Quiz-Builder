import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listStudySets } from "../api/client";
import type { StudySet } from "../types";
import { Card } from "../components/Card";

export default function StudySets() {
  const [items, setItems] = useState<StudySet[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;
    (async () => {
      const data = await listStudySets();
      if (mounted) {
        setItems(data);
        setLoading(false);
      }
    })();
    return () => {
      mounted = false;
    };
  }, []);

  return (
    <div className="grid gap-4">
      <div>
        <h1 className="text-xl font-semibold">Study Sets</h1>
        <p className="text-sm text-gray-600">Your saved sets (mock storage).</p>
      </div>

      {loading ? (
        <Card>Loading...</Card>
      ) : items.length === 0 ? (
        <Card>
          <p className="text-sm text-gray-700">
            No study sets yet. Go to <Link className="underline" to="/">Home</Link> to create one.
          </p>
        </Card>
      ) : (
        <div className="grid gap-3">
          {items.map((s) => (
            <Link key={s.id} to={`/study-sets/${s.id}`}>
              <Card className="hover:border-gray-300">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="font-medium">{s.title}</div>
                    <div className="text-xs text-gray-500">
                      {new Date(s.createdAt).toLocaleString()}
                    </div>
                  </div>
                  <span className="rounded-full bg-gray-100 px-2 py-1 text-xs text-gray-700">
                    {s.status}
                  </span>
                </div>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
