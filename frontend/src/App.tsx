import { BrowserRouter, Route, Routes } from "react-router-dom"
import { Board } from "./components/Board"
import { LandingPage } from "./components/LandingPage"

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/app" element={<Board />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App
