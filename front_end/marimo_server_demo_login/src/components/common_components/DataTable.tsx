// DataTable.tsx
import * as React from "react"
import {
  type ColumnDef,
  type ColumnFiltersState,
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  type SortingState,
  useReactTable,
  type VisibilityState,
} from "@tanstack/react-table"
import { ArrowUpDown, ChevronDown, MoreHorizontal, Play, StopCircle, RefreshCw } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Input } from "@/components/ui/input"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Badge } from "@/components/ui/badge"
import { getMyServers, checkMyServersStatus, listDocuments, JUPYTERHUB_URL } from "../../../api/request_methods"
import { useAuth0 } from "@auth0/auth0-react"
import type { ServerInfo, MyServersStatusResponse, DocumentInfo, ListDocumentsResponse } from "../../../api/types"

export default function ServersDataTable() {
  const [servers, setServers] = React.useState<ServerInfo[]>([])
  const [loading, setLoading] = React.useState(true)
  const [sorting, setSorting] = React.useState<SortingState>([])
  const [columnFilters, setColumnFilters] = React.useState<ColumnFiltersState>([])
  const [columnVisibility, setColumnVisibility] = React.useState<VisibilityState>({})
  const [rowSelection, setRowSelection] = React.useState({})
  const { getAccessTokenSilently } = useAuth0()

  const loadServers = async () => {
    try {
      setLoading(true)
      const token = await getAccessTokenSilently?.()
      const response = await getMyServers({ userToken: token })
      if (response.data?.ok && response.data.servers) {
        setServers(response.data.servers)
      }
    } catch (err) {
      console.error("Failed to load servers:", err)
    } finally {
      setLoading(false)
    }
  }

  React.useEffect(() => {
    loadServers()
  }, [getAccessTokenSilently])

  const columns: ColumnDef<ServerInfo>[] = [
    {
      id: "select",
      header: ({ table }) => (
        <Checkbox
          checked={table.getIsAllPageRowsSelected()}
          onCheckedChange={(value) => table.toggleAllPageRowsSelected(!!value)}
          aria-label="Select all"
        />
      ),
      cell: ({ row }) => (
        <Checkbox
          checked={row.getIsSelected()}
          onCheckedChange={(value) => row.toggleSelected(!!value)}
          aria-label="Select row"
        />
      ),
      enableSorting: false,
      enableHiding: false,
    },
    {
      accessorKey: "name",
      header: ({ column }) => {
        return (
          <Button
            variant="ghost"
            onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}
          >
            Server Name
            <ArrowUpDown className="ml-2 h-4 w-4" />
          </Button>
        )
      },
      cell: ({ row }) => {
        const name = row.getValue("name") as string
        return (
          <div className="font-medium">
            {name === "" ? "Default Server" : name}
          </div>
        )
      },
    },
    {
      accessorKey: "state",
      header: "Status",
      cell: ({ row }) => {
        const state = row.getValue("state") as string
        const ready = row.original.ready
        
        const getStatusVariant = (state: string, ready: boolean) => {
          if (ready) return "default"
          if (state === "pending") return "secondary"
          return "destructive"
        }

        const getStatusText = (state: string, ready: boolean) => {
          if (ready) return "Running"
          if (state === "pending") return "Starting"
          return "Stopped"
        }

        return (
          <Badge variant={getStatusVariant(state, ready)}>
            {getStatusText(state, ready)}
          </Badge>
        )
      },
    },
    {
      accessorKey: "started",
      header: "Started",
      cell: ({ row }) => {
        const started = row.getValue("started") as string
        return started ? new Date(started).toLocaleString() : "Not started"
      },
    },
    {
      accessorKey: "last_activity",
      header: "Last Activity",
      cell: ({ row }) => {
        const lastActivity = row.getValue("last_activity") as string
        return lastActivity ? new Date(lastActivity).toLocaleString() : "No activity"
      },
    },
    {
      accessorKey: "url",
      header: "Actions",
      cell: ({ row }) => {
        const server = row.original
        const isRunning = server.ready
        
        return (
          <div className="flex space-x-2">
            {isRunning && server.url && (
              <Button
                size="sm"
                variant="outline"
                onClick={() => {
                  // Construct absolute URL to JupyterHub server
                  const absoluteUrl = `${JUPYTERHUB_URL}${server.url}`
                  window.open(absoluteUrl, '_blank')
                }}
              >
                <Play className="h-4 w-4 mr-1" />
                Open
              </Button>
            )}
            <Button
              size="sm"
              variant="outline"
              onClick={loadServers}
            >
              <RefreshCw className="h-4 w-4" />
            </Button>
          </div>
        )
      },
    },
  ]

  const table = useReactTable({
    data: servers,
    columns,
    onSortingChange: setSorting,
    onColumnFiltersChange: setColumnFilters,
    getCoreRowModel: getCoreRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    onColumnVisibilityChange: setColumnVisibility,
    onRowSelectionChange: setRowSelection,
    state: {
      sorting,
      columnFilters,
      columnVisibility,
      rowSelection,
    },
  })

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="h-8 w-8 animate-spin" />
        <span className="ml-2">Loading servers...</span>
      </div>
    )
  }

  return (
    <div className="w-full">
      <div className="flex items-center py-4">
        <Input
          placeholder="Filter servers..."
          value={(table.getColumn("name")?.getFilterValue() as string) ?? ""}
          onChange={(event) =>
            table.getColumn("name")?.setFilterValue(event.target.value)
          }
          className="max-w-sm"
        />
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline" className="ml-auto">
              Columns <ChevronDown className="ml-2 h-4 w-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            {table
              .getAllColumns()
              .filter((column) => column.getCanHide())
              .map((column) => {
                return (
                  <DropdownMenuCheckboxItem
                    key={column.id}
                    className="capitalize"
                    checked={column.getIsVisible()}
                    onCheckedChange={(value) =>
                      column.toggleVisibility(!!value)
                    }
                  >
                    {column.id}
                  </DropdownMenuCheckboxItem>
                )
              })}
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            {table.getHeaderGroups().map((headerGroup) => (
              <TableRow key={headerGroup.id}>
                {headerGroup.headers.map((header) => {
                  return (
                    <TableHead key={header.id}>
                      {header.isPlaceholder
                        ? null
                        : flexRender(
                            header.column.columnDef.header,
                            header.getContext()
                          )}
                    </TableHead>
                  )
                })}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {table.getRowModel().rows?.length ? (
              table.getRowModel().rows.map((row) => (
                <TableRow
                  key={row.id}
                  data-state={row.getIsSelected() && "selected"}
                >
                  {row.getVisibleCells().map((cell) => (
                    <TableCell key={cell.id}>
                      {flexRender(
                        cell.column.columnDef.cell,
                        cell.getContext()
                      )}
                    </TableCell>
                  ))}
                </TableRow>
              ))
            ) : (
              <TableRow>
                <TableCell
                  colSpan={columns.length}
                  className="h-24 text-center"
                >
                  No servers found.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>
      <div className="flex items-center justify-end space-x-2 py-4">
        <div className="flex-1 text-sm text-muted-foreground">
          {table.getFilteredSelectedRowModel().rows.length} of{" "}
          {table.getFilteredRowModel().rows.length} row(s) selected.
        </div>
        <div className="space-x-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => table.previousPage()}
            disabled={!table.getCanPreviousPage()}
          >
            Previous
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => table.nextPage()}
            disabled={!table.getCanNextPage()}
          >
            Next
          </Button>
        </div>
      </div>
    </div>
  )
}

export function DocumentsDataTable() {
  const [documents, setDocuments] = React.useState<DocumentInfo[]>([])
  const [servers, setServers] = React.useState<ServerInfo[]>([])
  const [loading, setLoading] = React.useState(true)
  const [sorting, setSorting] = React.useState<SortingState>([])
  const [columnFilters, setColumnFilters] = React.useState<ColumnFiltersState>([])
  const [columnVisibility, setColumnVisibility] = React.useState<VisibilityState>({})
  const [rowSelection, setRowSelection] = React.useState({})
  const { getAccessTokenSilently } = useAuth0()

  const loadDocuments = async () => {
    try {
      setLoading(true)
      const token = await getAccessTokenSilently?.()

      // Load both documents and servers
      const [docsResponse, serversResponse] = await Promise.all([
        listDocuments({ userToken: token }),
        getMyServers({ userToken: token })
      ])

      if (docsResponse.data?.ok && docsResponse.data.documents) {
        setDocuments(docsResponse.data.documents)
      }

      if (serversResponse.data?.ok && serversResponse.data.servers) {
        setServers(serversResponse.data.servers)
      }
    } catch (err) {
      console.error("Failed to load documents:", err)
    } finally {
      setLoading(false)
    }
  }

  React.useEffect(() => {
    loadDocuments()
  }, [getAccessTokenSilently])

  // Get the first running server URL
  const getRunningServerUrl = () => {
    const runningServer = servers.find(server => server.ready && server.url)
    return runningServer?.url
  }

  const columns: ColumnDef<DocumentInfo>[] = [
    {
      id: "select",
      header: ({ table }) => (
        <Checkbox
          checked={table.getIsAllPageRowsSelected()}
          onCheckedChange={(value) => table.toggleAllPageRowsSelected(!!value)}
          aria-label="Select all"
        />
      ),
      cell: ({ row }) => (
        <Checkbox
          checked={row.getIsSelected()}
          onCheckedChange={(value) => row.toggleSelected(!!value)}
          aria-label="Select row"
        />
      ),
      enableSorting: false,
      enableHiding: false,
    },
    {
      accessorKey: "name",
      header: ({ column }) => {
        return (
          <Button
            variant="ghost"
            onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}
          >
            Document Name
            <ArrowUpDown className="ml-2 h-4 w-4" />
          </Button>
        )
      },
      cell: ({ row }) => {
        const name = row.getValue("name") as string
        return <div className="font-medium">{name}</div>
      },
    },
    {
      accessorKey: "size",
      header: ({ column }) => {
        return (
          <Button
            variant="ghost"
            onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}
          >
            Size
            <ArrowUpDown className="ml-2 h-4 w-4" />
          </Button>
        )
      },
      cell: ({ row }) => {
        const size = row.getValue("size") as number
        const formatSize = (bytes: number) => {
          if (bytes < 1024) return `${bytes} B`
          if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(2)} KB`
          return `${(bytes / (1024 * 1024)).toFixed(2)} MB`
        }
        return <div>{formatSize(size)}</div>
      },
    },
    {
      accessorKey: "modified",
      header: ({ column }) => {
        return (
          <Button
            variant="ghost"
            onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}
          >
            Last Modified
            <ArrowUpDown className="ml-2 h-4 w-4" />
          </Button>
        )
      },
      cell: ({ row }) => {
        const modified = row.getValue("modified") as number
        return <div>{new Date(modified * 1000).toLocaleString()}</div>
      },
    },
    {
      accessorKey: "path",
      header: "Actions",
      cell: ({ row }) => {
        const document = row.original
        const serverUrl = getRunningServerUrl()
        const hasRunningServer = !!serverUrl

        return (
          <div className="flex space-x-2">
            <Button
              size="sm"
              variant="outline"
              disabled={!hasRunningServer}
              onClick={() => {
                if (serverUrl) {
                  // Open the marimo notebook in edit mode on the spawned JupyterHub server
                  // Ensure the server URL ends with a slash for proper routing through JupyterHub proxy
                  const normalizedServerUrl = serverUrl.endsWith('/') ? serverUrl : `${serverUrl}/`

                  // Use the absolute path to ensure marimo can find the file
                  // Marimo accepts the file path via the ?file= query parameter
                  const marimoUrl = `${JUPYTERHUB_URL}${normalizedServerUrl}?file=${encodeURIComponent(document.path)}`
                  window.open(marimoUrl, '_blank')
                }
              }}
              title={hasRunningServer ? "Open marimo notebook" : "No running server available"}
            >
              <Play className="h-4 w-4 mr-1" />
              Open
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={loadDocuments}
              title="Refresh documents"
            >
              <RefreshCw className="h-4 w-4" />
            </Button>
          </div>
        )
      },
    },
  ]

  const table = useReactTable({
    data: documents,
    columns,
    onSortingChange: setSorting,
    onColumnFiltersChange: setColumnFilters,
    getCoreRowModel: getCoreRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    onColumnVisibilityChange: setColumnVisibility,
    onRowSelectionChange: setRowSelection,
    state: {
      sorting,
      columnFilters,
      columnVisibility,
      rowSelection,
    },
  })

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="h-8 w-8 animate-spin" />
        <span className="ml-2">Loading documents...</span>
      </div>
    )
  }

  return (
    <div className="w-full">
      <div className="flex items-center py-4">
        <Input
          placeholder="Filter documents..."
          value={(table.getColumn("name")?.getFilterValue() as string) ?? ""}
          onChange={(event) =>
            table.getColumn("name")?.setFilterValue(event.target.value)
          }
          className="max-w-sm"
        />
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline" className="ml-auto">
              Columns <ChevronDown className="ml-2 h-4 w-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            {table
              .getAllColumns()
              .filter((column) => column.getCanHide())
              .map((column) => {
                return (
                  <DropdownMenuCheckboxItem
                    key={column.id}
                    className="capitalize"
                    checked={column.getIsVisible()}
                    onCheckedChange={(value) =>
                      column.toggleVisibility(!!value)
                    }
                  >
                    {column.id}
                  </DropdownMenuCheckboxItem>
                )
              })}
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            {table.getHeaderGroups().map((headerGroup) => (
              <TableRow key={headerGroup.id}>
                {headerGroup.headers.map((header) => {
                  return (
                    <TableHead key={header.id}>
                      {header.isPlaceholder
                        ? null
                        : flexRender(
                            header.column.columnDef.header,
                            header.getContext()
                          )}
                    </TableHead>
                  )
                })}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {table.getRowModel().rows?.length ? (
              table.getRowModel().rows.map((row) => (
                <TableRow
                  key={row.id}
                  data-state={row.getIsSelected() && "selected"}
                >
                  {row.getVisibleCells().map((cell) => (
                    <TableCell key={cell.id}>
                      {flexRender(
                        cell.column.columnDef.cell,
                        cell.getContext()
                      )}
                    </TableCell>
                  ))}
                </TableRow>
              ))
            ) : (
              <TableRow>
                <TableCell
                  colSpan={columns.length}
                  className="h-24 text-center"
                >
                  No documents found.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>
      <div className="flex items-center justify-end space-x-2 py-4">
        <div className="flex-1 text-sm text-muted-foreground">
          {table.getFilteredSelectedRowModel().rows.length} of{" "}
          {table.getFilteredRowModel().rows.length} row(s) selected.
        </div>
        <div className="space-x-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => table.previousPage()}
            disabled={!table.getCanPreviousPage()}
          >
            Previous
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => table.nextPage()}
            disabled={!table.getCanNextPage()}
          >
            Next
          </Button>
        </div>
      </div>
    </div>
  )
}
