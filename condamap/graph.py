class DiGraph:
    """
    A simple unweighted directed graph.  
    """

    def __init__(self):
        """
        A DiGraph holds information about the directed connections
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

    def add_connections(self, 
                        source_name, 
                        dest_names):
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
