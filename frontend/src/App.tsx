import { Routes, Route } from "react-router-dom";
import Home from "./Home";
import Login from "./Login";
import DevoFeedback from "./DevoFeedback";
import SimpleTest from "./SimpleTest";
import DevoFeedbackEdit from "./DevoFeedbackEdit";


function App() {
  console.log("🚀 React app loaded via Vite");
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/login" element={<Login />} />
      <Route path="/react/devos-feedback" element={<DevoFeedback />} />
      <Route path="/react/devos-feedback/edit" element={<DevoFeedbackEdit />} />
      <Route path="/test" element={<SimpleTest />} />
    </Routes>
  );
}

export default App;