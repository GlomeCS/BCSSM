import { Routes, Route } from "react-router-dom";
import Home from "./Home";
import Login from "./Login";
import DevoFeedback from "./DevoFeedback";
import SimpleTest from "./SimpleTest";
import DevoFeedbackEdit from "./DevoFeedbackEdit";
import DutiesPage from "./DutiesPage";
import Sections from "./Sections";
import AdminPasswords from "./AdminPasswords";


function App() {
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/login" element={<Login />} />
      <Route path="/react/devos-feedback" element={<DevoFeedback />} />
      <Route path="/react/devos-feedback/edit" element={<DevoFeedbackEdit />} />
      <Route path="/duties" element={<DutiesPage />} />
      <Route path="/sections" element={<Sections />} />
      <Route path="/test" element={<SimpleTest />} />
      <Route path="/admin/passwords" element={<AdminPasswords />} />
    </Routes>
  );
}

export default App;