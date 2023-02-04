require 'nokogiri'

class ServerList
  def initialize(xml)
    @doc = Nokogiri::XML(xml)
  end 

  def remove(ids)
    @doc
      .css("ArrayOfServerItem ServerItem")
      .select { |e| ids.include?(e.at_css('id').content) }
      .each(&:remove)
  end
  
  def to_xml
    @doc.to_s
  end
end

require 'uri'
require 'net/http'
require 'json'

require 'date'

class Server
  MONTHS_TIL_EXPIRED = 3
  attr_reader :id, :last_seen

  def initialize(id: , last_seen:)
    @id = id
    @last_seen = last_seen
  end

  def expired?
    @last_seen <= DateTime.now.prev_month(MONTHS_TIL_EXPIRED)
  end
end

module TreeStats
  class Servers
    def self.all
      response = fetch
      parse(response.body)
    end

    def self.expired
      all.select(&:expired?)
    end
  
    def self.fetch
      Net::HTTP.get_response(URI('https://servers.treestats.net/api/servers/'))
    end
  
    def self.parse(body)
      JSON
        .parse(body)
        .map do |server| 
          Server.new(
            id: server['guid'],
            last_seen: DateTime.parse(server.dig('status', 'last_seen'))
          )
        end
    end
  end
end

FILE_PATH = '/github/workspace/Servers.xml'
KEEP_PATH = '/github/workspace/keep'

xml = File.read(FILE_PATH)
server_list = ServerList.new(xml)
expired = TreeStats::Servers.expired

require 'csv'
keep_ids = CSV.read(KEEP_PATH).flatten

ids = expired.map(&:id).reject { |id| keep_ids.include?(id) }
server_list.remove(ids)

File.write(FILE_PATH, server_list.to_xml)
