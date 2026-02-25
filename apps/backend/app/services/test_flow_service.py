# filepath: d:\project\nanotest\apps\backend\app\services\test_flow_service.py
"""Test flow service for business logic."""
from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy import select

from app.domain.models import TestFlow
from app.repositories.base import BaseRepository
from app.schemas.schemas import (
    TestFlowCreate, 
    TestFlowUpdate, 
    TestFlowResponse, 
    TestFlowListResponse,
    FlowGraphSchema,
)


class TestFlowRepository(BaseRepository[TestFlow]):
    """Repository for TestFlow operations."""
    
    def __init__(self, db: Session):
        super().__init__(TestFlow, db)
    
    def get_by_project(
        self, 
        project_id: UUID, 
        *, 
        skip: int = 0, 
        limit: int = 100
    ) -> List[TestFlow]:
        """Get all test flows for a project."""
        query = (
            select(TestFlow)
            .where(TestFlow.project_id == project_id)
            .offset(skip)
            .limit(limit)
        )
        result = self.db.execute(query)
        return list(result.scalars().all())
    
    def get_by_name(self, project_id: UUID, name: str) -> Optional[TestFlow]:
        """Get a test flow by name within a project."""
        query = select(TestFlow).where(
            TestFlow.project_id == project_id,
            TestFlow.name == name
        )
        result = self.db.execute(query)
        return result.scalar_one_or_none()


class TestFlowService:
    """Service for test flow operations."""
    
    def __init__(self, db: Session):
        self.db = db
        self.repository = TestFlowRepository(db)
    
    def create_test_flow(self, project_id: UUID, flow_data: TestFlowCreate) -> TestFlow:
        """Create a new test flow."""
        # Check if flow with same name exists
        existing = self.repository.get_by_name(project_id, flow_data.name)
        if existing:
            raise ValueError(f"Test flow with name '{flow_data.name}' already exists")
        
        # Validate flow graph
        validation_errors = self._validate_flow_graph(flow_data.graph)
        if validation_errors:
            raise ValueError(f"Invalid flow graph: {', '.join(validation_errors)}")
        
        flow_dict = flow_data.model_dump()
        flow_dict["project_id"] = project_id
        
        return self.repository.create(obj_in=flow_dict)
    
    def get_test_flow(self, flow_id: UUID) -> Optional[TestFlow]:
        """Get a test flow by ID."""
        return self.repository.get(flow_id)
    
    def list_test_flows(
        self, 
        project_id: UUID, 
        page: int = 1, 
        page_size: int = 20
    ) -> TestFlowListResponse:
        """List all test flows for a project with pagination."""
        skip = (page - 1) * page_size
        flows = self.repository.get_by_project(project_id, skip=skip, limit=page_size)
        total = self.repository.count(filters={"project_id": project_id})
        
        return TestFlowListResponse(
            items=[TestFlowResponse.model_validate(f) for f in flows],
            total=total,
            page=page,
            page_size=page_size,
        )
    
    def update_test_flow(
        self, 
        flow_id: UUID, 
        flow_data: TestFlowUpdate
    ) -> Optional[TestFlow]:
        """Update a test flow."""
        flow = self.repository.get(flow_id)
        if not flow:
            return None
        
        update_data = flow_data.model_dump(exclude_unset=True)
        
        # Validate flow graph if being updated
        if "graph" in update_data and update_data["graph"]:
            validation_errors = self._validate_flow_graph(FlowGraphSchema(**update_data["graph"]))
            if validation_errors:
                raise ValueError(f"Invalid flow graph: {', '.join(validation_errors)}")
        
        return self.repository.update(id=flow_id, obj_in=update_data)
    
    def delete_test_flow(self, flow_id: UUID) -> bool:
        """Delete a test flow."""
        return self.repository.delete(id=flow_id)
    
    def _validate_flow_graph(self, graph: FlowGraphSchema) -> List[str]:
        """Validate a flow graph structure."""
        errors = []
        
        if not graph.nodes:
            errors.append("Flow must have at least one node")
            return errors
        
        node_ids = {node.id for node in graph.nodes}
        
        # Check for start node
        start_nodes = [n for n in graph.nodes if n.type == "start"]
        if len(start_nodes) == 0:
            errors.append("Flow must have a start node")
        elif len(start_nodes) > 1:
            errors.append("Flow can only have one start node")
        
        # Validate edges reference existing nodes
        for edge in graph.edges or []:
            if edge.source not in node_ids:
                errors.append(f"Edge references non-existent source node: {edge.source}")
            if edge.target not in node_ids:
                errors.append(f"Edge references non-existent target node: {edge.target}")
        
        # Check for unreachable nodes (except start)
        if graph.edges:
            targets = {edge.target for edge in graph.edges}
            for node in graph.nodes:
                if node.type != "start" and node.id not in targets:
                    errors.append(f"Node '{node.id}' is unreachable")
        
        return errors
    
    def compile_flow(self, flow_id: UUID) -> dict:
        """Compile a flow into an executable format."""
        flow = self.repository.get(flow_id)
        if not flow:
            raise ValueError("Flow not found")
        
        # Build execution order using topological sort
        graph = flow.graph
        nodes = {n["id"]: n for n in graph.get("nodes", [])}
        edges = graph.get("edges", [])
        
        # Build adjacency list
        adj = {node_id: [] for node_id in nodes}
        in_degree = {node_id: 0 for node_id in nodes}
        
        for edge in edges:
            source, target = edge["source"], edge["target"]
            if source in adj and target in in_degree:
                adj[source].append(target)
                in_degree[target] += 1
        
        # Find start node
        start_node = None
        for node_id, node in nodes.items():
            if node.get("type") == "start":
                start_node = node_id
                break
        
        # Topological sort
        execution_order = []
        queue = [start_node] if start_node else [n for n, d in in_degree.items() if d == 0]
        
        while queue:
            node_id = queue.pop(0)
            execution_order.append(nodes[node_id])
            
            for neighbor in adj.get(node_id, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
        
        return {
            "flow_id": str(flow_id),
            "flow_name": flow.name,
            "execution_order": execution_order,
            "total_nodes": len(execution_order),
        }
