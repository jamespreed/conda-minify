class Node:
    """
    Node element for a graph.
    """
    __slots__ = ['_name', '_data']

    def __init__(self, name, data=None):
        """
        Node object with `name` and additional `data` such as attributes.  
        Each Node is uniquely defined by its `name`.  Comparing two nodes with
        the same name for equality will return True (data is not considered).
        """
        self._name = name
        self._data = data if data else {}

    def __repr__(self):
        return '<Node "{0}" at 0x{1:x}>'.format(self.name, id(self))

    def __hash__(self):
        return hash(self.name)

    @property
    def name(self):
        return self._name

    @property
    def data(self):
        return self._data.copy()


class Edge:
    """
    Edge element for a graph.
    """
    __slots__ = ['_source', '_dest', '_data']

    def __init__(self, source, dest, data=None):
        """
        Edge object from `source` to `dest` Node objects.  Additional
        attributes are stored in `data`.
        """
        self._source = source
        self._dest = dest
        self._data = data if data else {}

    def __repr__(self):
        return '<Edge source={0} dest={1} at 0x{2:x}>'.format(
                    self.source.name,
                    self.dest.name,
                    id(self)
                )

    def __hash__(self):
        return hash(self.source, self.dest)

    @property
    def source(self):
        return self._source

    @property
    def dest(self):
        return self._dest

    @property
    def data(self):
        return self._data.copy()


class DiGraph:
    """
    A simple directed graph.  
    """

    def __init__(self):
        """
        A DiGraph holds information about the directed connections
        between Nodes.
        """
        self._outward = {}
        self._inward = {}

    def __repr__(self):
        n = self.__class__.__name__
        return '<{0} at 0x{1:x}>'.format(n, id(self))

    def __contains__(self, item):
        if isinstance(item, str):
            item = Node(item)
        try:
            return self.has_node(item)
        except TypeError as e:
            e1 = e
        try:
            return self.has_node(item)
        except TypeError as e:
            e2 = e
        raise TypeError(e1.args + e2.args)

    def add_node(self, name, data=None):
        """
        Adds a single Node to the graph with `name` and `data` parameters.

        Returns: Node
        """
        node = Node(name, data)
        # check for existance
        if node in self._outward:
            return self._outward.get(node)
        self._outward.setdefault(node, {})
        self._inward.setdefault(node, {})
        return node

    def add_edge(self, source, dest, data=None):
        """
        Adds an Edge between two Nodes to the graph.  Both `source` and `dest`
        should be passed as `Node` objects.  `data` is additional data about
        the edge.

        Returns: Edge
        """
        edge = Edge(source, dest, data)
        self._outward[source].setdefault(dest, edge)
        return self._inward[dest].setdefault(source, edge)

    def has_node(self, node):
        if not isinstance(node, Node):
            raise TypeError('The `node` argument must be a Node type.')
        return node in self._outward

    def has_edge(self, edge):
        if not isinstance(edge, Edge):
            raise TypeError('The `edge` argument must be an Edge type.')
        return bool(self._outward.get(edge.source, {}).get(edge.dest))

    def add_connection(self,
                       source_name,
                       dest_name,
                       source_data=None,
                       dest_data=None,
                       edge_data=None):
        """
        Adds two nodes and an edge from `source` to `dest` to the graph.
        Optional data fields for the source, dest, and edge can be included.

        Returns: (Node <source>, Node <dest>, Edge)
        """
        n_s = self.add_node(source_name, source_data)
        n_d = self.add_node(dest_name, dest_data)
        e = self.add_edge(n_s, n_d, edge_data)
        return n_s, n_d, e

    def add_connections(self, 
                        source_name, 
                        dest_names, 
                        source_data=None,
                        dest_data_list=None):
        """
        Adds multiple connections from `source` to each dest in `dest_list`.
        If data is being added, the length of the `dest_data_list` must be
        the same as `dest_names`.  Edge data cannot be passed using this
        method.

        Returns: [(Node <source>, Node <dest>, Edge), ...]

        Examples:
        >>> dg = DiGraph()
        >>> dg.add_connections('a', ['b', 'c', 'd'], {'val': 1}, 
        ...     [{'val': 3}, {'val': 10}, {'val': 1}])
        """
        if not dest_data_list:
            dest_data_list = [None] * len(dest_names)
        assert len(dest_names) == len(dest_data_list)
        return [
            self.add_connection(
                source_name,
                dest_name,
                source_data,
                dest_data
            )
            for dest_name, dest_data in zip(dest_names, dest_data_list)
        ]

    def get_node_by_name(self, name):
        """
        Returns the node in the graph with `name` or None if the node is not
        in the graph.
        """
        node = Node(name)
        return self._outward.get(node)
