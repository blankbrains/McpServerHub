import { Routes, Route, Link, useLocation } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import Market from './pages/Market'
import ServerDetail from './pages/ServerDetail'
import MyServers from './pages/MyServers'

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/market" element={<Market />} />
        <Route path="/servers/:id" element={<ServerDetail />} />
        <Route path="/my-servers" element={<MyServers />} />
      </Routes>
    </Layout>
  )
}
