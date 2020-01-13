class DirectedGraph:
    """
    A simple unweighted directed graph.  
    """

    def __init__(self):
        """
        A DirectedGraph holds information about the directed connections
        between nodes.
        """
        self._outward = {}
        self._inward = {}

    def __repr__(self):
        n = self.__class__.__name__
        return '<{0} at 0x{1:x}>'.format(n, id(self))

    def __contains__(self, item):
        return item in self._outward

    @staticmethod
    def _norm(name):
        """Normalizes a node name"""
        return str(name).lower()

    def add_node(self, name):
        """
        Adds a single node to the graph. The `name` is converted to a lower-
        case string.
        """
        node = self._norm(name)
        # check for existance
        if node in self._outward:
            return node
        self._outward.setdefault(node, set())
        self._inward.setdefault(node, set())
        return node

    def add_edge(self, source, dest):
        """
        Adds an edge between two nodes to the graph.  Both `source` and `dest`
        will be converted to lower-case strings.

        Returns: source_node, dest_node
        """
        s_node = self.add_node(source)
        d_node = self.add_node(dest)
        self._outward[s_node].add(d_node)
        self._inward[d_node].add(s_node)
        return s_node, d_node

    def has_node(self, node):
        return self._norm(node) in self._outward

    def has_edge(self, source, dest):
        s = self._norm(source)
        d = self._norm(dest)
        return bool(d in self._outward.get(s, set()))

    def add_connections(self, source_name, dest_names):
        """
        Adds multiple connections from `source` to each dest in `dest_list`.

        Returns: [(source, dest), ...]

        Examples:
        >>> dg = DiGraph()
        >>> dg.add_connections('a', ['b', 'c', 'd'])
        """
        return [
            self.add_edge(source_name, dest_name)
            for dest_name in dest_names
        ]

    def find_path(self, start, end, path=None):
        """
        Finds the first available path from start to end; not always the 
        shortest.
        """
        if not path:
            path = []
        path = path + [start]
        if start == end:
            return path
        if not self._outward[start]:
            return []
        for node in self._outward[start]:
            if node not in path:
                newpath = self.find_path(node, end, path)
                if newpath: 
                    return newpath
        return None

class DirectedAcyclicGraph(DirectedGraph):
    """
    A simple unweighted directed acyclic graph.  
    """
    def __init__(self, on_cycle='ignore'):
        """
        A DAG holds information about the directed connections between nodes, 
        but does not allow cycles.

        :cycles: [str ('ignore', 'raise')]
            How to handle the attempt to add a cycle to the graph.  
              ignore - ignores the edge, does not add it to the graph.
              raise  - raises an error.
        """
        self._on_cycle = None
        self.on_cycle = on_cycle
        super().__init__()

    @property
    def on_cycle(self):
        return self._on_cycle

    @on_cycle.setter
    def on_cycle(self, value):
        allowed = ('ignore', 'raise')
        if value not in allowed:
            raise ValueError(
                'The cycles property can only have values from: '
                '{0}'.format(allowed)
            )
        self._on_cycle = value

    def add_edge(self, source, dest):
        """
        Adds an edge between two nodes to the graph.  Both `source` and `dest`
        will be converted to lower-case strings.

        Returns: source_node, dest_node
        """
        self.add_node(source)
        self.add_node(dest)
        if self._check_cycle(source, dest):
            return super().add_edge(source, dest)
        return None

    def _detect_backedge(self, source, dest):
        """
        Returns True if adding an edge from `s` to `d` would create a 
        backedge which instantiate a cycle.
        """
        # try to run a path from d to s, if connected, it would be a backedge 
        return bool(self.find_path(dest, source))

    def _check_cycle(self, source, dest):
        c = self._detect_backedge(source, dest)
        if not c:
            return True
        if c and (self.on_cycle == 'ignore'):
            return False
        raise CycleError('Add an edge from "{0}" to "{1}" would create a '
            'cycle in the DirectedAcyclicGraph'.format(source, dest))

class CycleError(ValueError):
    pass