import { Link, Route, Routes } from "react-router-dom";
import Home from "./pages/Home";
import StudySetDetail from "./pages/StudySetDetail";

export default function App() {
  return (
    <div className="min-h-screen bg-gray-50">
      <header className="border-b bg-white">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-4">
          <Link to="/" className="text-lg font-semibold">
            AI Quiz Builder
          </Link>
          <nav className="flex gap-4 text-sm">
            <Link className="text-gray-600 hover:text-black" to="/">
              Home
            </Link>
          </nav>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-4 py-6">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/study-sets/:id" element={<StudySetDetail />} />
        </Routes>
      </main>
    </div>
  );
}
