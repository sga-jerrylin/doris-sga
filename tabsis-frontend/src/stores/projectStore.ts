import { defineStore } from 'pinia'
import { ref } from 'vue'
import axios from 'axios'

const API_BASE = (import.meta.env.VITE_API_BASE_URL || '/api').trim() || '/api'

export const useProjectStore = defineStore('project', () => {
    const projects = ref<any[]>([])
    const currentProject = ref<any | null>(null)
    const currentCompany = ref<any | null>(null)
    const companies = ref<any[]>([])

    async function fetchProjects() {
        const res = await axios.get(`${API_BASE}/projects`)
        projects.value = res.data
    }

    async function fetchProject(id: number) {
        const res = await axios.get(`${API_BASE}/projects/${id}`)
        currentProject.value = res.data
        // Also fetch companies for this project
        const resCompanies = await axios.get(`${API_BASE}/projects/${id}/companies`)
        companies.value = resCompanies.data
        if (companies.value.length > 0) {
            currentCompany.value = companies.value[0]
        } else {
            currentCompany.value = null
        }
    }

    async function fetchCompany(id: number) {
        const res = await axios.get(`${API_BASE}/companies/${id}`)
        currentCompany.value = res.data
    }

    async function createProject(name: string, description: string) {
        const res = await axios.post(`${API_BASE}/projects`, { name, description })
        await fetchProjects()
        return res.data
    }

    async function createCompany(projectId: number, name: string, taxId: string, backgroundInfo: string) {
        const res = await axios.post(`${API_BASE}/projects/${projectId}/companies`, {
            name,
            tax_id: taxId,
            background_info: backgroundInfo
        })
        await fetchProject(projectId)
        return res.data
    }

    function setCurrentCompany(company: any) {
        currentCompany.value = company
    }

    return {
        projects,
        currentProject,
        currentCompany,
        companies,
        fetchProjects,
        fetchProject,
        fetchCompany,
        createProject,
        createCompany,
        setCurrentCompany
    }
})
